# Pona Survey — Tableau Dashboard Guide

Run `generate_charts.py` first — it outputs two Tableau-ready CSVs to `data/`.

## Data sources

| File | Use |
|---|---|
| `data/tableau_survey_clean.csv` | One row per respondent. Fields: sub_id, condition_short, failed_class, hardest_part, ideal_solution, submitted_at |
| `data/tableau_methods_exploded.csv` | One row per method per respondent (for counting multi-select answers). Fields: sub_id, condition_short, method |

Connect both as separate data sources in Tableau. Join on `sub_id` if you want to cross-filter by condition.

---

## Dashboard 1 — Who responded?

**Chart type:** Horizontal bar chart
**Data source:** `tableau_survey_clean.csv`
**Dimension:** `condition_short`
**Measure:** `COUNT(sub_id)`
**Sort:** Descending by count
**Color:** Single teal (`#2A9D8F`) or gradient by count

---

## Dashboard 2 — How do people check?

**Chart type:** Horizontal bar chart
**Data source:** `tableau_methods_exploded.csv`
**Dimension:** `method`
**Measure:** `COUNT(sub_id)`
**Sort:** Descending by count
**Note:** This is multi-select data — one respondent can appear in multiple bars. Add a subtitle: *"Multi-select — respondents could choose all that apply"*

---

## Dashboard 3 — Has the approach ever failed?

**Chart type:** Donut / pie chart
**Data source:** `tableau_survey_clean.csv`
**Dimension:** `failed_class`
**Measure:** `COUNT(sub_id)`
**Colors:**
- Yes → `#E76F51` (coral)
- No → `#2A9D8F` (teal)
- Partial / N/A → `#F59E0B` (amber)

To make a donut in Tableau: duplicate the measure on the Rows shelf, use dual-axis, set the inner circle to white with a smaller size.

---

## Dashboard 4 — Quote highlights

Build this as a text dashboard in Tableau:
- Insert a text object with each quote in italic
- Use a dark background (`#264653`) with white text
- Add a teal horizontal rule above each quote using a blank sheet with a coloured reference line

Or use the PNG output from `generate_charts.py` directly — it's already LinkedIn-ready.

---

## Recommended Tableau layout

- Combine all 4 charts on a single Tableau story (4 story points)
- Use a consistent dark header (`#264653`) with white title text
- Add a filter action: clicking a condition in Dashboard 1 highlights that condition in Dashboard 2
- Set canvas size to 1080×1080px for square LinkedIn screenshots
