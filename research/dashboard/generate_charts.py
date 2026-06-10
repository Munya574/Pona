"""
Pona User Research — LinkedIn Carousel + Tableau Export
Run: python generate_charts.py
Outputs 5 PNG slides (1080x1080) to output/ and Tableau-ready CSVs to data/
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
DATA = ROOT / "data" / "survey_raw.csv"
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

# ── Brand palette ──────────────────────────────────────────────────────────────
TEAL      = "#2A9D8F"
TEAL_MID  = "#54C8BE"
TEAL_PALE = "#9FE8E3"
DARK      = "#264653"
GRAY      = "#6B7280"
GRAY_LT   = "#E5E7EB"
WHITE     = "#FFFFFF"
BG        = "#F8FFFE"
AMBER     = "#F59E0B"
CORAL     = "#E76F51"

SIZE = (10.8, 10.8)
DPI = 100

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica Neue", "Helvetica"],
})

# ── Load & clean ───────────────────────────────────────────────────────────────
df = pd.read_csv(DATA, encoding="utf-8-sig")
df.columns = [
    "sub_id", "resp_id", "submitted_at", "condition",
    "hardest_part", "check_methods", "approach_failed", "ideal_solution",
]
n = len(df)

# Shorten condition labels
COND_MAP = {
    "I manage another dietary restriction":                    "Other dietary restriction",
    "Someone close to me does (not me personally)":            "Someone close to me",
    "I manage lactose intolerance":                            "Lactose intolerance",
    "I manage a food allergy (e.g. nuts, shellfish, gluten)":  "Food allergy",
    "I manage acid reflux or GERD":                            "Acid reflux / GERD",
}
df["condition_short"] = df["condition"].map(COND_MAP).fillna(df["condition"])

# Multi-select: split, explode, count
METHOD_MAP = {
    "Read the label carefully":             "Read the label",
    "Google it":                            "Google it",
    "Ask the staff or whoever made it":     "Ask staff / maker",
    "Avoid anything I'm uncertain about":   "Avoid uncertain food",
    "Avoid anything Im uncertain about":    "Avoid uncertain food",
    "Use an app":                           "Use an app",
}
methods_raw = (
    df["check_methods"]
    .dropna()
    .str.split(",")
    .explode()
    .str.strip()
)
methods_raw = methods_raw.map(lambda x: METHOD_MAP.get(x, x))
method_counts = methods_raw.value_counts()
# Collapse any residual duplicates after mapping
method_counts = method_counts.groupby(method_counts.index).sum()
method_counts = method_counts.sort_values(ascending=True)

# Classify "has approach failed" — hand-verified against each response
FAIL_MAP = {
    "Z9N7ovz": "Partial / N/A",   # describes workaround, no clear fail
    "Ardg2oe": "Partial / N/A",   # empty response
    "OQz2XDg": "No",
    "Nq6jADO": "Partial / N/A",   # overwhelming but no reaction
    "LDbepNp": "Yes",             # bought wrong product unknowingly
    "rD6zVjo": "Yes",             # explicitly says yes
    "LDbQ19z": "Yes",             # mild reaction after confirming with staff
    "Gez2dqp": "Yes",             # discovered more restrictions after symptoms
    "Arl2Vro": "No",
    "yXl4eVB": "Yes",             # "sometimes" — had to work around it
    "2j4KLkg": "Yes",             # staff left out details, got a reaction
    "1WrVgGL": "Yes",             # bloated, cramps, headache
    "Z9d6JEa": "Partial / N/A",   # empty / not personal restriction
    "KpMlLaX": "Yes",             # got a reaction
    "peLBWgV": "No",
    "ArlLq9N": "No",
    "peLBvXJ": "No",
    "LDdWqdz": "Yes",             # overlooks milk content
    "kbY76Xj": "Yes",             # frequently sick despite checking
    "2j42qEV": "Yes",             # missed things, had allergic reaction
}
df["failed_class"] = df["sub_id"].map(FAIL_MAP).fillna("Partial / N/A")

FAIL_ORDER  = ["Yes", "No", "Partial / N/A"]
FAIL_COLORS = [CORAL, TEAL, AMBER]
fail_vals   = [df["failed_class"].value_counts().get(k, 0) for k in FAIL_ORDER]


# ── Layout helpers ─────────────────────────────────────────────────────────────
def make_fig(bg=BG):
    return plt.figure(figsize=SIZE, facecolor=bg)


def header_band(fig, title, subtitle, tag):
    ax = fig.add_axes([0, 0.845, 1, 0.155])
    ax.set_facecolor(DARK)
    ax.axis("off")
    ax.text(0.055, 0.72, title,   transform=ax.transAxes,
            fontsize=28, fontweight="bold", color=WHITE,    va="center")
    ax.text(0.055, 0.25, subtitle, transform=ax.transAxes,
            fontsize=13, color=TEAL_PALE, va="center")
    ax.text(0.950, 0.72, tag,     transform=ax.transAxes,
            fontsize=13, color=GRAY,      va="center", ha="right")


def footer_band(fig, bg=BG):
    ax = fig.add_axes([0, 0, 1, 0.052])
    ax.set_facecolor(DARK)
    ax.axis("off")
    ax.text(
        0.055, 0.5,
        f"n={n}  ·  qualitative survey  ·  Pona user research  ·  May–June 2026",
        transform=ax.transAxes, fontsize=11, color=GRAY, va="center",
    )
    ax.text(0.945, 0.5, "pona", transform=ax.transAxes,
            fontsize=14, fontweight="bold", color=TEAL, va="center", ha="right")


def hbar_axes(fig):
    return fig.add_axes([0.04, 0.09, 0.88, 0.73])


def style_hbar(ax, counts):
    ax.set_facecolor(BG)
    ax.set_xlim(0, counts.max() + 3)
    ax.tick_params(axis="y", labelsize=16, colors=DARK)
    ax.tick_params(axis="x", bottom=False, labelbottom=False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(axis="x", color=GRAY_LT, zorder=1, linewidth=0.8)


def hbar_palette(n_bars):
    pool = [TEAL_PALE, TEAL_PALE, TEAL_MID, TEAL_MID, TEAL]
    return pool[-n_bars:]


def value_labels(ax, bars, values):
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + 0.15,
            bar.get_y() + bar.get_height() / 2,
            str(val), va="center", ha="left",
            fontsize=24, fontweight="bold", color=DARK,
        )


# ── Slide 0 — Title ────────────────────────────────────────────────────────────
def s0_title():
    fig = make_fig(bg=DARK)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(DARK)
    ax.axis("off")

    ax.text(0.5, 0.87, "pona",
            ha="center", va="center", transform=ax.transAxes,
            fontsize=72, fontweight="bold", color=TEAL)
    ax.text(0.5, 0.79, "to heal  ·  to get well",
            ha="center", va="center", transform=ax.transAxes,
            fontsize=17, color=GRAY, style="italic")

    # Divider
    div = fig.add_axes([0.25, 0.733, 0.50, 0.0025])
    div.set_facecolor(TEAL)
    div.axis("off")

    ax.text(
        0.5, 0.585,
        f"What {n} people told me\nabout checking if food is safe",
        ha="center", va="center", transform=ax.transAxes,
        fontsize=36, fontweight="bold", color=WHITE, linespacing=1.5,
    )
    ax.text(
        0.5, 0.415,
        "User research conducted before writing a single line of code",
        ha="center", va="center", transform=ax.transAxes,
        fontsize=16, color=GRAY,
    )

    badge = FancyBboxPatch(
        (0.27, 0.295), 0.46, 0.068,
        transform=ax.transAxes, clip_on=False,
        boxstyle="round,pad=0.015",
        facecolor="#1B3340", edgecolor=TEAL, linewidth=1.5,
    )
    ax.add_patch(badge)
    ax.text(0.5, 0.330, f"n={n}  ·  May–June 2026  ·  qualitative",
            ha="center", va="center", transform=ax.transAxes,
            fontsize=14, color=TEAL_PALE)

    fig.savefig(OUT / "slide_00_title.png", dpi=DPI, bbox_inches="tight", facecolor=DARK)
    plt.close(fig)
    print(f"  slide 00 — title")


# ── Slide 1 — Who responded ────────────────────────────────────────────────────
def s1_who():
    counts = df["condition_short"].value_counts().sort_values()

    fig = make_fig()
    header_band(fig, "Who responded?",
                "Self-reported conditions managed by survey respondents", "1 / 4")
    footer_band(fig)

    ax = hbar_axes(fig)
    palette = hbar_palette(len(counts))
    bars = ax.barh(counts.index, counts.values,
                   color=palette, height=0.55, zorder=2)
    value_labels(ax, bars, counts.values)
    style_hbar(ax, counts)

    fig.savefig(OUT / "slide_01_who.png", dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  slide 01 — who responded")


# ── Slide 2 — How people check ────────────────────────────────────────────────
def s2_methods():
    fig = make_fig()
    header_band(fig, "How do people currently check food safety?",
                "Multi-select — respondents could choose all that apply", "2 / 4")
    footer_band(fig)

    ax = hbar_axes(fig)
    palette = hbar_palette(len(method_counts))
    bars = ax.barh(method_counts.index, method_counts.values,
                   color=palette, height=0.55, zorder=2)
    value_labels(ax, bars, method_counts.values)
    style_hbar(ax, method_counts)

    fig.savefig(OUT / "slide_02_methods.png", dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  slide 02 — check methods")


# ── Slide 3 — Has it failed? ──────────────────────────────────────────────────
def s3_failed():
    fig = make_fig()
    header_band(fig, "Has the usual approach ever failed?",
                "Did checking still result in a reaction or missed restriction?", "3 / 4")
    footer_band(fig)

    ax = fig.add_axes([0.15, 0.09, 0.70, 0.73])
    ax.set_facecolor(BG)
    ax.set_aspect("equal")

    wedges, _, autotexts = ax.pie(
        fail_vals,
        labels=None,
        colors=FAIL_COLORS,
        autopct=lambda p: f"{p:.0f}%" if p > 0 else "",
        startangle=90,
        explode=[0.03, 0.03, 0.03],
        wedgeprops={"linewidth": 5, "edgecolor": BG},
        pctdistance=0.68,
        textprops={"fontsize": 22, "fontweight": "bold", "color": WHITE},
    )

    # Donut hole
    hole = plt.Circle((0, 0), 0.42, color=BG)
    ax.add_artist(hole)
    ax.text(0,  0.06, str(n),           ha="center", va="center",
            fontsize=34, fontweight="bold", color=DARK)
    ax.text(0, -0.14, "respondents",    ha="center", va="center",
            fontsize=13, color=GRAY)

    patches = [
        mpatches.Patch(color=c, label=f"{l}  ({v})")
        for c, l, v in zip(FAIL_COLORS, FAIL_ORDER, fail_vals)
    ]
    ax.legend(handles=patches, loc="lower center",
              bbox_to_anchor=(0.5, -0.22), ncol=3, fontsize=14,
              frameon=False, labelcolor=DARK)

    fig.savefig(OUT / "slide_03_failed.png", dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  slide 03 — approach failed")


# ── Slide 4 — Quotes ──────────────────────────────────────────────────────────
def s4_quotes():
    QUOTES = [
        (
            "Take a pic and have it tell me\nif it's good or not.",
            "Respondent managing dietary restrictions",
        ),
        (
            "If you have GERD, don't consume.\nIf you're lactose intolerant, don't consume.",
            "Respondent managing acid reflux / GERD",
        ),
        (
            "Clear gluten-free labeling on\nEVERYTHING that's GF.",
            "Respondent managing celiac disease",
        ),
    ]

    fig = make_fig(bg=DARK)
    header_band(fig, "In their own words",
                "What respondents said they actually want", "4 / 4")
    footer_band(fig, bg=DARK)

    ax = fig.add_axes([0, 0.052, 1, 0.793])
    ax.set_facecolor(DARK)
    ax.axis("off")

    y_positions = [0.76, 0.46, 0.16]
    for (quote, attr), y in zip(QUOTES, y_positions):
        # Teal accent bar
        ax.plot([0.07, 0.18], [y + 0.095, y + 0.095],
                color=TEAL, linewidth=4, transform=ax.transAxes,
                solid_capstyle="round")
        ax.text(0.07, y + 0.045,
                f'"{quote}"',
                transform=ax.transAxes, ha="left", va="top",
                fontsize=19, color=WHITE, style="italic", linespacing=1.55)
        ax.text(0.07, y - 0.068,
                f"— {attr}",
                transform=ax.transAxes, ha="left", va="top",
                fontsize=12, color=GRAY)

    fig.savefig(OUT / "slide_04_quotes.png", dpi=DPI, bbox_inches="tight", facecolor=DARK)
    plt.close(fig)
    print(f"  slide 04 — quotes")


# ── Tableau export ─────────────────────────────────────────────────────────────
def export_tableau():
    # 1. Clean main table
    clean = df[[
        "sub_id", "condition_short", "failed_class",
        "hardest_part", "ideal_solution", "submitted_at",
    ]].copy()
    clean.to_csv(ROOT / "data" / "tableau_survey_clean.csv", index=False)

    # 2. Exploded methods table (one row per method per respondent)
    exploded = (
        df[["sub_id", "condition_short", "check_methods"]]
        .copy()
        .assign(method=df["check_methods"].str.split(","))
        .explode("method")
    )
    exploded["method"] = (
        exploded["method"]
        .str.strip()
        .map(lambda x: METHOD_MAP.get(x, x) if pd.notna(x) else x)
    )
    exploded = exploded.dropna(subset=["method"])
    exploded.to_csv(ROOT / "data" / "tableau_methods_exploded.csv", index=False)

    print("  Tableau CSVs -> data/tableau_survey_clean.csv + tableau_methods_exploded.csv")


# ── Run all ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Loaded {n} survey responses.\nGenerating slides...")
    s0_title()
    s1_who()
    s2_methods()
    s3_failed()
    s4_quotes()
    export_tableau()
    print(f"\nDone. PNG slides -> {OUT.resolve()}")
