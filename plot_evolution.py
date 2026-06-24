"""
plot_evolution.py
Reads OpenEvolve checkpoint data and plots the evolution curve.
Run with:  uv run python plot_evolution.py
Output:    config/openevolve_output/evolution_curve.png
"""
import os
import json
import glob
import matplotlib
matplotlib.use("Agg")          # non-interactive backend — works without a display
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── paths ──────────────────────────────────────────────────────────────────────
CHECKPOINT_ROOT = os.path.join("config", "openevolve_output", "checkpoints")
OUTPUT_PNG      = os.path.join("config", "openevolve_output", "evolution_curve.png")

# ── collect best score at each checkpoint ──────────────────────────────────────
def load_checkpoints():
    pattern = os.path.join(CHECKPOINT_ROOT, "checkpoint_*", "best_program_info.json")
    files   = sorted(glob.glob(pattern),
                     key=lambda p: int(os.path.basename(os.path.dirname(p)).split("_")[-1]))
    data = []
    for f in files:
        with open(f) as fp:
            info = json.load(fp)
        iteration = int(os.path.basename(os.path.dirname(f)).split("_")[-1])
        score     = info.get("metrics", {}).get("combined_score", None)
        gen       = info.get("generation", None)
        if score is not None:
            data.append({"iteration": iteration, "score": score, "generation": gen})
    return data

# ── collect archive size at each checkpoint ────────────────────────────────────
def load_archive_sizes():
    pattern = os.path.join(CHECKPOINT_ROOT, "checkpoint_*", "programs")
    dirs    = sorted(glob.glob(pattern),
                     key=lambda p: int(os.path.basename(os.path.dirname(p)).split("_")[-1]))
    sizes = []
    for d in dirs:
        iteration = int(os.path.basename(os.path.dirname(d)).split("_")[-1])
        count     = len(glob.glob(os.path.join(d, "*.json")))
        sizes.append({"iteration": iteration, "archive_size": count})
    return sizes

# ── draw ───────────────────────────────────────────────────────────────────────
def draw(checkpoints, archive_sizes):
    iters  = [d["iteration"] for d in checkpoints]
    scores = [d["score"]     for d in checkpoints]

    arc_iters = [d["iteration"]    for d in archive_sizes]
    arc_sizes = [d["archive_size"] for d in archive_sizes]

    NAVY   = "#0D2137"
    TEAL   = "#00C896"
    BLUE   = "#1A6BAF"
    ORANGE = "#D4730A"
    GREY   = "#B8C8D8"

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                   gridspec_kw={"height_ratios": [3, 1]})
    fig.patch.set_facecolor(NAVY)
    for ax in (ax1, ax2):
        ax.set_facecolor(NAVY)
        ax.tick_params(colors=GREY)
        ax.spines["bottom"].set_color(GREY)
        ax.spines["left"].set_color(GREY)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    # ── top: evolution curve ──
    ax1.plot(iters, scores, color=TEAL, linewidth=2.5, marker="o",
             markersize=7, zorder=3, label="Best combined_score")
    ax1.axhline(y=0.9525, color=ORANGE, linewidth=1.5, linestyle="--", zorder=2)
    ax1.axvline(x=32,     color=ORANGE, linewidth=1.0, linestyle=":",  zorder=2)
    ax1.axhline(y=0.847,  color=BLUE,   linewidth=1.5, linestyle="--", zorder=2, alpha=0.7)

    # annotate best
    ax1.annotate("BEST: 0.9525\n(iter 32, gen 1)",
                 xy=(32, 0.9525), xytext=(35, 0.940),
                 arrowprops=dict(arrowstyle="->", color=ORANGE),
                 color=ORANGE, fontsize=9, fontweight="bold")

    # annotate baseline
    ax1.annotate("Assignment 1 baseline: 0.847",
                 xy=(iters[0], 0.847), xytext=(iters[0] + 2, 0.850),
                 color=BLUE, fontsize=8, alpha=0.9)

    ax1.set_ylabel("combined_score", color=GREY, fontsize=11)
    ax1.set_ylim(0.82, 0.97)
    ax1.set_xlim(0, 55)
    ax1.yaxis.label.set_color(GREY)
    ax1.set_title(
        "OpenEvolve Evolution Curve\n"
        "AgentSociety Challenge — 50 Iterations, 3 Islands, MAP-Elites",
        color="white", fontsize=13, fontweight="bold", pad=12
    )

    legend_patches = [
        mpatches.Patch(color=TEAL,   label="Best combined_score per checkpoint"),
        mpatches.Patch(color=ORANGE, label="Best score = 0.9525 (iter 32)"),
        mpatches.Patch(color=BLUE,   label="Assignment 1 baseline = 0.847"),
    ]
    ax1.legend(handles=legend_patches, facecolor=NAVY,
               edgecolor=GREY, labelcolor=GREY, fontsize=9, loc="lower right")
    ax1.grid(axis="y", color=GREY, alpha=0.15, linestyle="--")

    # ── bottom: archive size ──
    ax2.bar(arc_iters, arc_sizes, color=BLUE, alpha=0.8, width=3, zorder=3)
    ax2.set_ylabel("Archive size", color=GREY, fontsize=9)
    ax2.set_xlabel("Iteration", color=GREY, fontsize=11)
    ax2.set_xlim(0, 55)
    ax2.set_ylim(0, 20)
    ax2.yaxis.label.set_color(GREY)
    ax2.xaxis.label.set_color(GREY)
    ax2.grid(axis="y", color=GREY, alpha=0.10, linestyle="--")

    # annotation for final archive
    if arc_sizes:
        ax2.annotate(f"Final: {arc_sizes[-1]} programs",
                     xy=(arc_iters[-1], arc_sizes[-1]),
                     xytext=(arc_iters[-1] - 18, arc_sizes[-1] + 1.5),
                     arrowprops=dict(arrowstyle="->", color=TEAL),
                     color=TEAL, fontsize=8)

    plt.tight_layout(pad=2.0)
    os.makedirs(os.path.dirname(OUTPUT_PNG), exist_ok=True)
    plt.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight", facecolor=NAVY)
    print(f"Saved → {OUTPUT_PNG}")


# ── main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    checkpoints   = load_checkpoints()
    archive_sizes = load_archive_sizes()

    if not checkpoints:
        print("No checkpoint data found. Run OpenEvolve first.")
        raise SystemExit(1)

    print(f"Found {len(checkpoints)} checkpoints:")
    for d in checkpoints:
        print(f"  iter={d['iteration']:>3}  score={d['score']:.4f}  gen={d['generation']}")

    print(f"\nFinal archive size: {archive_sizes[-1]['archive_size']} programs")
    draw(checkpoints, archive_sizes)
