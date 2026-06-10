# Pona

A mobile-first food safety app that helps people with dietary restrictions quickly determine whether a food is safe for them to eat.

**Name origin:** "Pona" means "to heal" in Zambian Tonga.

## What it does

Scan any food — by photo, ingredient label, or recipe URL — and get an instant Safe / Caution / Unsafe verdict personalised to your sensitivity profile. Covers 25+ conditions including allergies, intolerances, GERD, FODMAPs, histamine, gout, and more.

## Stack

- **Frontend:** React + Vite + Tailwind CSS
- **Backend:** FastAPI (Python)
- **ML:** PyTorch (CV), DistilBERT (NLP), Tesseract (OCR), FAISS (vector search)
- **Database:** PostgreSQL
- **Deployment:** Vercel (frontend), Render (backend)

## Project structure

```
pona/
├── frontend/        # React + Vite + Tailwind
├── backend/         # FastAPI + ML pipeline
├── notebooks/       # Data exploration & model training
└── data/            # Raw and processed datasets (gitignored if large)
```

## Getting started

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Build order

1. Frontend UI
2. Backend API skeleton
3. Sensitivity knowledge base
4. NLP normalization model
5. CV model
6. Substitution system
