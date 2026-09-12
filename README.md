# Pona

Checks whether a food contains something **you** react to — and nothing else.

**Name origin:** "Pona" means "to heal" in Zambian Tonga.

**Live:** [pona-t.vercel.app](https://pona-t.vercel.app) · API: [pona-api.onrender.com](https://pona-api.onrender.com/health)
*(free-tier hosting — the first request after a quiet period takes ~30s to wake)*

**[→ Research and decision log](research/DECISIONS.md)** — how 20 survey responses drove what got built, what got cut, and what the result measures.

---

## What it does

Scan a barcode, photograph an ingredient label, or paste the text. Pona tells you what it found relative to your profile, and — importantly — what it **could not** check.

It also generates a **chef card**: your profile rendered for a restaurant kitchen, including the hidden names an allergen hides under and the specific questions worth asking.

## What it deliberately does not do

This scope is the product, not a limitation:

- **It does not rate food.** No score, no grade, no "good" or "bad". Pona answers one question — does this contain something on your profile — and has no opinion on whether you should eat it.
- **It never says "safe".** Results are `no triggers found` / `possible triggers` / `contains trigger`. "Safe" would claim far more than was checked.
- **It does not assert triggers you did not give it.** Conditions where triggers are individual (reflux) ship with no built-in list. You add what *you* react to.
- **It does not include claims the evidence does not support.** MSG sensitivity and gout were removed on those grounds, with the reasoning recorded in the data files.

## Measured

Benchmarked against Open Food Facts products where a person independently recorded which allergens are present.

| | |
|---|---|
| Allergen recall, English labels | **94.5%** (95.6% including cross-contamination flags) |
| Measured over | 22,799 allergen tags on real products |
| Label photo reading | 71.7% — which is why extracted text is always shown for review |
| Non-English labels | **27.3%** — a known defect, reported separately rather than averaged away |
| Conditions covered | 13, each scoped to a specific ingredient with regulator support |

Reproduce with `python notebooks/benchmark_matcher.py` (needs the Open Food Facts export).

## Architecture

```
frontend/          React + Vite + Tailwind, mobile-first
backend/
  app/ml/
    matcher.py           rule-based ingredient → condition matching
    ocr.py               label photo → text, with completeness gating
    barcode.py           barcode → Open Food Facts lookup
    chef_card.py         profile → something a kitchen can read
    substitution.py      alternatives, filtered by the user's own profile
    knowledge/           hand-curated source: conditions, synonyms, rules
  routers/               FastAPI endpoints
notebooks/         benchmarks and data analysis
research/          survey data, findings, decision log
```

**No ML model at runtime.** A fine-tuned DistilBERT normalizer was built, evaluated at **F1 = 0.0**, and replaced with rules that score 94.5%. The rules are also auditable, which matters when the output is a safety decision someone may need to question. `torch`, `transformers` and `faiss` were removed — nothing imports them.

### Endpoints

```
GET    /conditions/                     conditions Pona can check (from the KB, never hardcoded in the UI)
POST   /profile/                        create a profile
GET    /profile/{id}                    read a profile
PUT    /profile/{id}                    update conditions and personal triggers
GET    /profile/{id}/chef-card          the profile, rendered for a kitchen
POST   /verdict/                        check ingredients against a profile
GET    /scan/capabilities               what input methods actually work on this server
POST   /scan/barcode                    barcode → product + ingredients
POST   /scan/ocr                        label photo → text + confidence + warnings
```

`/scan/photo` (food recognition) and `/scan/url` (recipe pages) return **501 — not implemented**.

## Design principle: fail closed, never fail quiet

Every bug found in this project has had the same shape — confidently reporting that a food was fine when nothing had actually been checked. Four were found and fixed:

1. The knowledge base was gitignored, so a fresh clone loaded an empty KB and cleared **every** allergen. It now raises at startup instead.
2. An unrecognised condition was skipped with a log line. It is now named in the result and forces the verdict off "no triggers found".
3. A user-defined condition with no triggers set reported nothing found — when nothing had been looked for.
4. OCR reported **93.7% confidence while silently dropping PEANUTS** from a label. Mean confidence cannot see words that were never detected, so a separate completeness check now looks for the structural signs of dropped text.

Each has a regression test.

## Running it

Needs Python 3.11+, Node 18+. Tesseract is optional — without it, `/scan/capabilities` reports `ocr: false` and the UI hides the camera button rather than offering something that cannot work.

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload

# frontend (separate terminal)
cd frontend
npm install
npm run dev                                       # proxies /api → localhost:8000
```

Or with Docker, which includes Tesseract:

```bash
cd backend && docker build -t pona-api . && docker run -p 8000:8000 pona-api
```

### Tests

```bash
cd backend
python test_matcher.py    # 44 checks — what the matcher believes about food
python test_api.py        # 24 checks — database, profiles, verdicts, chef card
python test_ocr.py        # 13 checks — OCR safety gating
```

`test_matcher.py` tests false positives as heavily as false negatives. A matcher that flags everything is as dangerous as one that flags nothing — it teaches users to dismiss warnings.

## Known limitations

- **The knowledge base is seed data and has not been clinically reviewed.** It was assembled from food-regulator guidance (FDA major allergens, sulfite labelling, gluten-free labelling). It needs sign-off from a dietitian or allergist before anyone relies on it.
- **Non-English labels: 27.3% recall.** The knowledge base is English-only.
- **Label photo reading is ~72%** on real packaging. The extracted text is always shown for review before anything is matched.
- **Barcode data can be stale.** A lookup returns what a community database recorded; manufacturers reformulate without changing the barcode. The record's age is shown and the user confirms before checking.
- **No accounts.** The profile id lives in browser storage.

## Status

In development. Built: matching engine, profiles, personal triggers, verdicts, label OCR, barcode lookup, chef card. Next: substitutions (engine written, not yet exposed), menu scanning, recipe checking, trigger discovery.
