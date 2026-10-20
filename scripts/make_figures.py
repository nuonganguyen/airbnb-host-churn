"""Figures for reports/writeup.md, from saved backtest results (no refitting).

    .venv/bin/python scripts/make_figures.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
BT = PROJECT / "data_local" / "backtest"
OUT = PROJECT / "reports" / "figures"

# reference palette (dataviz skill), validated: blue/orange pass all checks on #fcfcfb
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = {"lgbm": ("LightGBM risk ranking", "#2a78d6"), "rule:low_presence_365": ("Best simple rule", "#eb6834")}


def load():
    frames = []
    for name in ("dev", "holdout"):
        m = pd.read_csv(BT / f"{name}_metrics.csv").query("variant == 'retain'")
        f = pd.read_csv(BT / f"{name}_folds.csv").query("variant == 'retain'")
        w = m.pivot(index="quarter", columns="model", values="host_p@500")
        w["random"] = f.set_index("quarter")["host_base_rate"]
        frames.append(w.assign(split=name))
    df = pd.concat(frames)
    df.index = pd.PeriodIndex(df.index, freq="Q")
    return df.reindex(pd.period_range(df.index.min(), df.index.max(), freq="Q"))  # gaps stay NaN


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = load()
    x = range(len(df))
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    hold = [i for i, s in enumerate(df["split"]) if s == "holdout"]
    ax.axvspan(hold[0] - 0.5, hold[-1] + 0.5, color="#f1f0ec", zorder=0, lw=0)
    ax.text(hold[0] - 0.35, 0.97, "Holdout\n(run once)", color=INK2, fontsize=8, va="top")
    ax.plot(x, df["random"], color=MUTED, lw=1.5, ls=(0, (3, 2)), zorder=2)
    for col, (label, color) in SERIES.items():
        ax.plot(x, df[col], color=color, lw=2, marker="o", ms=4.5, mec=SURFACE, mew=1.2, zorder=3, label=label)
    ax.plot([], [], color=MUTED, lw=1.5, ls=(0, (3, 2)), label="Random contact (expected)")
    last = len(df) - 1
    for col, (label, color) in SERIES.items():
        ax.annotate(f"{df[col].iloc[-1]:.2f}", (last, df[col].iloc[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=INK)
    q1 = list(df.index.astype(str)).index("2023Q1")
    ax.annotate("2023-Q1: suspected\nsource break", (q1, df["lgbm"].iloc[q1]), xytext=(-62, -6),
                textcoords="offset points", fontsize=7.5, color=INK2, ha="right", va="center",
                arrowprops=dict(arrowstyle="-", color=AXIS, lw=0.8))
    gaps = [i for i in x if pd.isna(df["lgbm"].iloc[i])]
    if gaps:
        ax.text(sum(gaps) / len(gaps), 0.05, "no usable\nfollow-up", color=MUTED, fontsize=7, ha="center")
    ticks = [i for i, q in enumerate(df.index) if q.quarter == 1]
    ax.set_xticks(ticks, [str(df.index[i].year) for i in ticks], fontsize=8, color=INK2)
    ax.set_ylim(0, 1)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"], fontsize=8, color=INK2)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(length=0)
    ax.set_title("Share of 500 contacted hosts with a listing that later disappears, by quarter",
                 loc="left", fontsize=10, color=INK, pad=22)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 1.08), ncol=3, frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    path = OUT / "host_precision_by_quarter.png"
    fig.savefig(path, facecolor=SURFACE)
    df.drop(columns="split").round(3).to_csv(OUT / "host_precision_by_quarter.csv", index_label="quarter")
    print(path)


if __name__ == "__main__":
    main()
