# Fake News Detector 🔍

A Streamlit web app that detects fake news using RoBERTa, Google Fact Check API, and Hindi language support.

## Stack
- **Model**: `hamzab/roberta-fake-news-classification` (HuggingFace)
- **Frontend**: Streamlit
- **Fact Check**: Google Fact Check Tools API
- **Translation**: deep-translator (for Hindi input)
- **Dataset**: ISOT (44k articles)

## Project Structure
```
fake-news-detector/
├── data/
│   ├── raw/          ← Put True.csv and Fake.csv here
│   └── processed/    ← Auto-generated splits
├── src/
│   ├── preprocess.py ← Day 1: EDA & cleaning
│   └── predict.py    ← Day 2: Model inference
├── app/
│   └── app.py        ← Day 3+: Streamlit UI
├── requirements.txt
└── README.md
```

## Setup
```bash
pip install -r requirements.txt
```

## Usage
```bash
# Day 1 — Preprocess
python src/preprocess.py

# Run app
streamlit run app/app.py
```
Input claim
    │
    ▼
Web search for the claim
    │
    ├── Found on Reuters/BBC/AP/PIB/WHO?  ──► HIGH credibility → lean REAL
    │
    ├── Found ONLY on unknown/sus sites?  ──► LOW credibility → lean FAKE
    │
    ├── Found nowhere at all?             ──► UNVERIFIABLE → flag as suspicious
    │
    └── Found but contradicted by         ──► DEBUNKED → FAKE
        credible sources?
    │
    ▼
ML classifier runs on the TEXT regardless
    │
    ▼
Combine both signals → Final verdict




Layer 1 — Web Search (ground truth check)
  Google Search API or SerpAPI
  → Is this claim on credible sites?

Layer 2 — Fact Check DB (already debunked?)
  Google Fact Check API (you already have this)
  → Has someone already debunked this exact claim?

Layer 3 — ML Model (linguistic patterns)
  Your fine-tuned RoBERTa
  → Does the text itself read like fake news?

Layer 4 — Heuristic Boost (Indian context)
  indian_fake_news_boost()
  → Does it have WhatsApp/India-specific patterns?

Final verdict = weighted combination of all 4


-future prospects
scraping of indian news and training
web search
image and video input allowed
improved efficiency

