import os
import re
import sys
from collections import Counter
from statistics import mean, stdev
from typing import Any, Iterable

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from websocietysimulator.agent import SimulationAgent
from src.flows.serving_flow import AgentSocietyServingFlow, InferenceState
from src.tools.interaction_tool_wrapper import inject_simulator_tool


MAX_HISTORY_REVIEWS = 12
MAX_REVIEW_TEXT_CHARS = 360
MAX_ITEM_CATEGORIES_CHARS = 240


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    """Read a key from a dict-or-object without raising."""
    if obj is None:
        return default
    for key in keys:
        if isinstance(obj, dict):
            if key in obj and obj[key] is not None:
                return obj[key]
        else:
            value = getattr(obj, key, None)
            if value is not None:
                return value
    return default


def _parse_item_avg_stars(item_summary: str) -> float | None:
    m = re.search(r"avg_stars=([\d.]+)", item_summary or "")
    if not m:
        return None
    try:
        return max(1.0, min(5.0, float(m.group(1))))
    except ValueError:
        return None


def _star_prior(user_avg: float | None, item_avg: float | None, fallback: float,
                review_count: int = 0) -> float:
    """Blend user history with item public average — adaptive weights by review count."""
    u = float(user_avg) if user_avg is not None else float(fallback)
    u = max(1.0, min(5.0, u))
    if item_avg is None:
        return u
    i = max(1.0, min(5.0, float(item_avg)))
    # Users with more reviews have a more reliable personal average → trust it more
    if review_count >= 50:
        w_user = 0.55
    elif review_count >= 15:
        w_user = 0.45
    else:
        w_user = 0.30
    blended = w_user * u + (1.0 - w_user) * i
    return max(1.0, min(5.0, blended))


def _calibration_block(prior: float) -> str:
    return (
        "\n\n=== STAR RATING PRIOR (data-driven estimate) ===\n"
        f"PRIOR_STAR_ESTIMATE: {prior:.2f}\n"
        "This prior blends the user's personal rating history with the business's public average. "
        "Use it as your starting point for the star prediction.\n"
        "Adjust UP if the business profile strongly matches the user's stated preferences "
        "or if USER_CATEGORY_SPECIFIC_AVERAGE is higher than the overall average.\n"
        "Adjust DOWN if peer reviews reveal clear problems (poor service, food quality, cleanliness) "
        "that align with topics this user cares about.\n"
        "Do NOT default to 3.0 or 4.0 without reading the evidence — commit to the most justified value.\n"
    )


def _snap_star_bucket(value: float) -> float:
    """Return one of {1.0, 2.0, 3.0, 4.0, 5.0}."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 4.0
    v = max(1.0, min(5.0, v))
    return float(int(round(v)))


def _sentiment_score(text: str) -> int:
    text_l = (text or "").lower()
    positive_words = [
        "love", "loved", "great", "good", "amazing", "tasty", "fresh",
        "friendly", "awesome", "delicious", "recommend", "excellent",
        "perfect", "wonderful", "fantastic", "superb", "best", "favorite",
        "outstanding", "brilliant", "impressive", "enjoyed", "pleased",
        "happy", "solid", "nice", "yummy", "warm", "clean", "fast",
    ]
    negative_words = [
        "bad", "awful", "terrible", "bland", "salty", "overcooked", "dry",
        "slow", "rude", "disappoint", "disappointed", "worst", "wait",
        "mediocre", "poor", "horrible", "disgusting", "avoid", "never",
        "overpriced", "cold", "dirty", "unfriendly", "pathetic", "gross",
        "stale", "undercooked", "soggy", "greasy", "loud", "cramped",
    ]
    pos = sum(1 for w in positive_words if w in text_l)
    neg = sum(1 for w in negative_words if w in text_l)
    return pos - neg


def _is_star_sentiment_conflict(stars: float, review: str) -> bool:
    score = _sentiment_score(review)
    if stars >= 4.0:
        return score < 0
    if stars <= 2.0:
        return score > 0
    return abs(score) >= 3


def _summarize_user(user: Any) -> str:
    if not user:
        return "User profile is unavailable. Treat the user as an unknown reviewer."

    name = _safe_get(user, "name", default="Unknown")
    review_count = _safe_get(user, "review_count", default="?")
    yelping_since = _safe_get(user, "yelping_since", default="?")
    avg_stars = _safe_get(user, "average_stars", "avg_stars", default=None)
    avg_str = f"{float(avg_stars):.2f}" if avg_stars is not None else "?"
    useful = _safe_get(user, "useful", default=0)
    funny = _safe_get(user, "funny", default=0)
    cool = _safe_get(user, "cool", default=0)
    fans = _safe_get(user, "fans", default=0)
    elite = _safe_get(user, "elite", default="") or "none"

    return (
        f"name={name}; review_count={review_count}; yelping_since={yelping_since}; "
        f"average_stars={avg_str}; useful={useful}; funny={funny}; cool={cool}; "
        f"fans={fans}; elite={elite}"
    )


def _summarize_item(item: Any) -> str:
    if not item:
        return "Item details are unavailable. Do not invent attributes."

    fields: list[str] = []
    name = _safe_get(item, "name")
    if name:
        fields.append(f"name={name}")
    city = _safe_get(item, "city")
    state = _safe_get(item, "state")
    if city or state:
        fields.append(f"location={city or '?'}, {state or '?'}")
    stars = _safe_get(item, "stars")
    if stars is not None:
        fields.append(f"avg_stars={stars}")
    review_count = _safe_get(item, "review_count")
    if review_count is not None:
        fields.append(f"review_count={review_count}")
    categories = _safe_get(item, "categories")
    if categories:
        fields.append(f"categories={_truncate(str(categories), MAX_ITEM_CATEGORIES_CHARS)}")
    attributes = _safe_get(item, "attributes")
    if isinstance(attributes, dict):
        price = attributes.get("RestaurantsPriceRange2")
        noise = attributes.get("NoiseLevel")
        attire = attributes.get("RestaurantsAttire")
        ambience = attributes.get("Ambience")
        if price:
            fields.append(f"price_range={price}")
        if noise:
            fields.append(f"noise={noise}")
        if attire:
            fields.append(f"attire={attire}")
        if ambience:
            fields.append(f"ambience={_truncate(str(ambience), 120)}")

    return "; ".join(fields) if fields else "Item exists but no descriptive fields are available."


def _summarize_peer_item_reviews(
    item_reviews: list,
    *,
    exclude_user_id: str,
    max_snippets: int = 5,
    max_chars: int = 240,
) -> str:
    """Short excerpts from other users' reviews of the same item."""
    if not item_reviews:
        return ""
    lines: list[str] = []
    for rev in item_reviews:
        uid = str(_safe_get(rev, "user_id", default="") or "")
        if exclude_user_id and uid == str(exclude_user_id):
            continue
        stars = _safe_get(rev, "stars", default="?")
        text = _truncate(str(_safe_get(rev, "text", default="")), max_chars)
        if not text:
            continue
        lines.append(f"- [{stars}* other reviewer] {text}")
        if len(lines) >= max_snippets:
            break
    if not lines:
        return ""
    return "\n".join(lines)


def _peer_avg_stars(peer_reviews: list, exclude_user_id: str) -> float | None:
    stars = []
    for rev in peer_reviews:
        if str(_safe_get(rev, "user_id", default="") or "") == str(exclude_user_id):
            continue
        try:
            s = float(_safe_get(rev, "stars", default=0) or 0)
            if 1.0 <= s <= 5.0:
                stars.append(s)
        except (TypeError, ValueError):
            pass
    return round(mean(stars), 2) if stars else None


def _rating_distribution(reviews: Iterable) -> str:
    buckets: Counter = Counter()
    total = 0
    for review in reviews:
        stars = _safe_get(review, "stars")
        if stars is None:
            continue
        try:
            star_int = int(round(float(stars)))
        except (TypeError, ValueError):
            continue
        if 1 <= star_int <= 5:
            buckets[star_int] += 1
            total += 1
    if total == 0:
        return "no rated history"
    parts = [f"{star}*={buckets.get(star, 0)}" for star in range(5, 0, -1)]
    return f"n={total}; " + ", ".join(parts)


def _star_mode(star_values: list[float]) -> float | None:
    if not star_values:
        return None
    counts: Counter = Counter(int(round(s)) for s in star_values)
    modal_star, modal_count = counts.most_common(1)[0]
    if modal_count >= 3:
        return float(modal_star)
    return None


def _summarize_history(reviews: list, item_categories: str = "") -> tuple:
    if not reviews:
        return ("No prior reviews are available for this user.", None)

    sorted_reviews = sorted(
        reviews,
        key=lambda r: str(_safe_get(r, "date", default="")),
        reverse=True,
    )

    star_values: list[float] = []
    for review in sorted_reviews:
        try:
            star_values.append(float(_safe_get(review, "stars", default=0) or 0))
        except (TypeError, ValueError):
            continue
    user_avg = mean(star_values) if star_values else None

    distribution = _rating_distribution(sorted_reviews)

    variance_str = ""
    if len(star_values) >= 2:
        sd = stdev(star_values)
        label = "consistent" if sd < 1.0 else "variable"
        variance_str = f"USER_RATING_VARIANCE: {sd:.2f} ({label} rater — {'narrow range' if sd < 1.0 else 'wide swings between low and high ratings'})"

    mode = _star_mode(star_values)

    word_counts: list[int] = []
    for rev in sorted_reviews[:MAX_HISTORY_REVIEWS]:
        text = str(_safe_get(rev, "text", default="") or "")
        if text:
            word_counts.append(len(text.split()))
    avg_words = int(mean(word_counts)) if word_counts else None

    sample_lines: list[str] = [
        f"TOTAL_HISTORICAL_REVIEWS={len(sorted_reviews)}",
        f"USER_HISTORICAL_AVERAGE_STARS={user_avg:.2f}" if user_avg is not None else "USER_HISTORICAL_AVERAGE_STARS=unknown",
    ]
    if mode is not None:
        sample_lines.append(
            f"USER_MODAL_STARS: {mode:.1f} (their most frequent rating — strong predictor of next rating)"
        )
    if variance_str:
        sample_lines.append(variance_str)
    sample_lines.append(f"USER_RATING_DISTRIBUTION: {distribution}")
    if avg_words is not None:
        sample_lines.append(
            f"USER_TYPICAL_WORD_COUNT: ~{avg_words} words per review (mirror this length in the generated review)"
        )

    # Category-specific average: scan review texts for item category keywords
    if item_categories:
        cat_keywords = [
            kw.strip().lower()
            for kw in item_categories.replace(",", " ").split()
            if len(kw.strip()) > 3
        ][:6]
        if cat_keywords:
            cat_stars: list[float] = []
            for rev in sorted_reviews:
                text_lower = str(_safe_get(rev, "text", default="") or "").lower()
                if any(kw in text_lower for kw in cat_keywords):
                    try:
                        s = float(_safe_get(rev, "stars", default=0) or 0)
                        if s > 0:
                            cat_stars.append(s)
                    except (TypeError, ValueError):
                        pass
            if len(cat_stars) >= 2:
                cat_avg = mean(cat_stars)
                sample_lines.append(
                    f"USER_CATEGORY_SPECIFIC_AVERAGE: {cat_avg:.2f} "
                    f"(from {len(cat_stars)} past reviews mentioning similar venues — "
                    f"prefer this over overall average when predicting stars)"
                )

    sample_lines.append("RECENT_REVIEWS (most recent first):")
    for review in sorted_reviews[:MAX_HISTORY_REVIEWS]:
        stars = _safe_get(review, "stars", default="?")
        date = _safe_get(review, "date", default="?")
        text = _truncate(str(_safe_get(review, "text", default="")), MAX_REVIEW_TEXT_CHARS)
        sample_lines.append(f"- [{stars}* on {date}] {text}")
    return ("\n".join(sample_lines), user_avg)


class CrewAISimulationAgent(SimulationAgent):
    """Adapter connecting AgentSociety's simulator framework to the CrewAI flow.

    All data retrieval happens deterministically BEFORE the crew runs, so agents
    receive real Yelp data as template variables — no tool calls needed inside the crew.
    """

    def __init__(self, llm: Any = None) -> None:
        super().__init__(llm)

    def _resolve_ids(self) -> tuple:
        if isinstance(self.task, dict):
            return (
                str(self.task.get("user_id", "") or ""),
                str(self.task.get("item_id", "") or ""),
            )
        return (
            str(getattr(self.task, "user_id", "") or ""),
            str(getattr(self.task, "item_id", "") or ""),
        )

    def _safe_call(self, func, *args, **kwargs):
        if func is None:
            return None
        try:
            return func(*args, **kwargs)
        except Exception:
            return None

    def workflow(self) -> dict:
        user_id, item_id = self._resolve_ids()

        inject_simulator_tool(getattr(self, "interaction_tool", None))

        tool = getattr(self, "interaction_tool", None)
        user    = self._safe_call(getattr(tool, "get_user",    None), user_id=user_id)
        item    = self._safe_call(getattr(tool, "get_item",    None), item_id=item_id)
        reviews = self._safe_call(getattr(tool, "get_reviews", None), user_id=user_id) or []

        user_summary = _summarize_user(user)
        item_summary = _summarize_item(item)

        peer_reviews = self._safe_call(getattr(tool, "get_reviews", None), item_id=item_id) or []
        peer_blob = _summarize_peer_item_reviews(peer_reviews, exclude_user_id=user_id)
        peer_avg = _peer_avg_stars(peer_reviews, exclude_user_id=user_id)
        if peer_avg is not None:
            item_summary += f"\nPEER_AVG_STARS: {peer_avg} (mean star rating across other reviewers of this business)"
        if peer_blob:
            item_summary = (
                item_summary
                + "\n\n=== OTHER REVIEWERS ABOUT THIS BUSINESS (snippets; topical context only) ===\n"
                + peer_blob
            )

        item_categories = str(_safe_get(item, "categories", default="") or "")
        history_summary, user_avg = _summarize_history(reviews, item_categories=item_categories)

        fallback_rating = (
            float(user_avg)
            if user_avg is not None
            else float(_safe_get(user, "average_stars", "avg_stars", default=4.0) or 4.0)
        )
        fallback_rating = max(1.0, min(5.0, fallback_rating))

        item_avg_stars = _parse_item_avg_stars(item_summary)
        prior = _star_prior(user_avg, item_avg_stars, fallback_rating,
                            review_count=len(reviews))
        history_with_prior = history_summary + _calibration_block(prior)

        mode = os.environ.get("CREWAI_PROCESS_MODE", "sequential").strip().lower()

        if mode == "parallel":
            from src.flows.parallel_flow import YelpParallelFlow, ParallelState
            flow = YelpParallelFlow(initial_state=ParallelState(
                user_id=user_id,
                item_id=item_id,
                user_summary=user_summary,
                item_summary=item_summary,
                history_summary=history_with_prior,
                fallback_rating=prior,
            ))
        else:
            initial_state = InferenceState(
                user_id=user_id,
                item_id=item_id,
                user_summary=user_summary,
                item_summary=item_summary,
                history_summary=history_with_prior,
                fallback_rating=prior,
            )
            flow = AgentSocietyServingFlow(initial_state=initial_state)

        final_state_dict = flow.kickoff()

        stars  = _snap_star_bucket(final_state_dict.get("predicted_rating", prior))
        review = str(final_state_dict.get("generated_review", "")) or "No review generated."

        # One controlled retry if sentiment obviously conflicts with stars
        if _is_star_sentiment_conflict(stars, review):
            repair_hint = (
                "\n\nCONSISTENCY_REPAIR_MODE=ON\n"
                f"Previous predicted stars: {stars:.1f}\n"
                f"Previous generated review: {review}\n"
                "Regenerate with strict sentiment-star consistency and keep item facts grounded.\n"
                "Do not invent attributes not present in ITEM DETAILS.\n"
            )
            repaired_state = InferenceState(
                user_id=user_id,
                item_id=item_id,
                user_summary=user_summary,
                item_summary=item_summary,
                history_summary=history_with_prior + repair_hint,
                fallback_rating=stars,
            )
            repaired_flow = AgentSocietyServingFlow(initial_state=repaired_state)
            repaired = repaired_flow.kickoff()
            stars  = _snap_star_bucket(repaired.get("predicted_rating", stars))
            review = str(repaired.get("generated_review", "")) or review

        return {
            "stars":  stars,
            "review": review,
        }
