from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_yelp_dataset(raw_dir: Path, out_dir: Path, top_cities: set[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    biz_in = raw_dir / "yelp_academic_dataset_business.json"
    usr_in = raw_dir / "yelp_academic_dataset_user.json"
    rev_in = raw_dir / "yelp_academic_dataset_review.json"

    item_out   = out_dir / "item.json"
    review_out = out_dir / "review.json"
    user_out   = out_dir / "user.json"

    for file_path in (biz_in, usr_in, rev_in):
        if not file_path.exists():
            raise FileNotFoundError(f"Missing Yelp raw file: {file_path}")

    # 1) Filter businesses by city -> item.json; collect allowed business IDs
    allowed_biz: set[str] = set()
    with biz_in.open("r", encoding="utf-8") as f, item_out.open("w", encoding="utf-8") as w:
        for line in f:
            x = json.loads(line)
            if x.get("city") in top_cities:
                x["item_id"] = x.pop("business_id")
                x["source"] = "yelp"
                x["type"]   = "business"
                allowed_biz.add(x["item_id"])
                w.write(json.dumps(x, ensure_ascii=False) + "\n")

    print(f"  businesses kept : {len(allowed_biz)}")

    # 2) Filter reviews by allowed business -> review.json; collect user IDs
    allowed_users: set[str] = set()
    rev_count = 0
    with rev_in.open("r", encoding="utf-8") as f, review_out.open("w", encoding="utf-8") as w:
        for line in f:
            x = json.loads(line)
            bid = x.get("business_id")
            if bid in allowed_biz:
                x["item_id"] = x.pop("business_id")
                x["source"] = "yelp"
                x["type"]   = "business"
                uid = x.get("user_id")
                if uid:
                    allowed_users.add(uid)
                w.write(json.dumps(x, ensure_ascii=False) + "\n")
                rev_count += 1

    print(f"  reviews kept    : {rev_count}")

    # 3) Filter users who appear in filtered reviews -> user.json
    usr_count = 0
    with usr_in.open("r", encoding="utf-8") as f, user_out.open("w", encoding="utf-8") as w:
        for line in f:
            x = json.loads(line)
            if x.get("user_id") in allowed_users:
                x["source"] = "yelp"
                w.write(json.dumps(x, ensure_ascii=False) + "\n")
                usr_count += 1

    print(f"  users kept      : {usr_count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build yelp_dataset/{item,review,user}.json from raw Yelp Academic Dataset files."
    )
    parser.add_argument(
        "--raw-dir",
        default="data/raw_yelp",
        help="Directory containing yelp_academic_dataset_*.json files.",
    )
    parser.add_argument(
        "--out-dir",
        default="yelp_dataset",
        help="Output directory for item.json, review.json, user.json.",
    )
    parser.add_argument(
        "--cities",
        nargs="+",
        default=["Philadelphia", "Tampa", "Tucson"],
        help="City names to include.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_dir   = Path(args.raw_dir).expanduser().resolve()
    out_dir   = Path(args.out_dir).expanduser().resolve()
    top_cities = {city.strip() for city in args.cities if city.strip()}

    if not top_cities:
        raise ValueError("At least one city is required via --cities.")

    print(f"Raw dir    : {raw_dir}")
    print(f"Output dir : {out_dir}")
    print(f"Cities     : {sorted(top_cities)}")
    build_yelp_dataset(raw_dir=raw_dir, out_dir=out_dir, top_cities=top_cities)
    print(f"Done: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
