# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (includes pytesseract — also install the Tesseract OCR binary, see below)
pip install -r requirements.txt

# Run the web app (main entry point)
streamlit run app/app.py

# Data preprocessing (requires True.csv and Fake.csv in data/raw/)
python src/preprocess.py

# Fine-tune RoBERTa on ISOT dataset (saves to models/fine_tuned/)
python src/train.py

# Run inference benchmark on 500 articles
python test_model.py

# Standalone module self-tests
python src/autopsy.py
python src/emotion.py
python src/who_benefits.py
python src/whatsapp_decode.py
```

### Tesseract OCR (Windows)

`pytesseract` is a Python wrapper — it needs the Tesseract binary installed separately.

1. Download the installer from <https://github.com/UB-Mannheim/tesseract/wiki>
2. Install to the default path: `C:\Program Files\Tesseract-OCR\`
3. During install, tick **Hindi** under "Additional language data" if you want OCR for Devanagari screenshots.
4. Add `C:\Program Files\Tesseract-OCR\` to your PATH, or set `pytesseract.pytesseract.tesseract_cmd` in `src/whatsapp_decode.py`.

When Tesseract isn't available, `ocr_image()` returns an empty string and the app shows a friendly warning — it does not crash.

## Architecture

**DeCypher** is a Streamlit web app for fake-news detection with an editorial broadsheet UI (`app/app.py` + `app/styles.css`). The analysis pipeline runs 8 parallel signals on user-submitted text:

1. **RoBERTa classifier** (`src/predict.py`) — loads `hamzab/roberta-fake-news-classification`, preferring the fine-tuned checkpoint at `models/fine_tuned/`. CPU path applies int8 dynamic quantization for ~2–3× speedup. Returns `{label, confidence, fake_prob, real_prob}` in [0,1].
2. **Google Fact Check API** (`src/fact_check.py`) — runs in parallel with RoBERTa via `ThreadPoolExecutor`. Requires `GOOGLE_FACT_CHECK_API_KEY` in `.env`. Gracefully skipped when absent.
3. **Bias heuristics** (`app/app.py:detect_bias`) — rule-based scan for emotional language, clickbait, absolute claims, capitalisation, us-vs-them rhetoric.
4. **AI-slop detection** (`app/app.py:detect_ai_slop`) — 0–100 based on hedging phrases, sentence length, absent contractions.
5. **Misinformation Autopsy** (`src/autopsy.py`) — rule-based detector that labels rhetorical weapons: fear-mongering, false urgency, cherry-picked statistics, appeal to (unnamed) authority, dehumanisation. Returns per-weapon `{intensity, detail, snippets}`.
6. **Emotional Trajectory** (`src/emotion.py`) — NRC-lite lexicon, sliding-window emotion intensity → curve + composite manipulation score. Real journalism is flat; propaganda has engineered peaks.
7. **Who Benefits?** (`src/who_benefits.py`) — entity extraction via `data/political_affiliations.json` curated lookup. Maps mentioned parties / leaders / corporates / media houses to political beneficiaries.
8. **Scam detector** (`src/scam_detector.py`) — Indian-specific OTP / KYC / lottery / UPI / APK / investment-scam patterns.

**WhatsApp tab pipeline:** `src/whatsapp_decode.py:normalise_whatsapp()` strips emoji clutter, decases shouting, expands SMS-speak / Hinglish shorthand, collapses runaway punctuation — *before* the model sees the text. `ocr_image()` extracts text from uploaded screenshots (English + Hindi).

**Hindi/multi-script support:** `src/translator.py` detects 9 Indian scripts (Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam) and auto-translates to English via deep-translator before inference.

**Indian content boost:** `app/app.py:indian_fake_news_boost` applies up to +0.60 to the RoBERTa fake probability when Indian-specific misinformation signals are detected (WhatsApp forward language, govt impersonation, health misinformation, financial panic).

### Key files

| File | Role |
|------|------|
| `app/app.py` | Streamlit UI; broadsheet editorial design with 9 sections (masthead → hero → stakes → analyser → method → record → margin → field reports → viral feed → sources → FAQ → footer) |
| `app/styles.css` | Single source of truth for visual styling. Bone/ink/vermilion/yellow palette; Instrument Serif + Space Grotesk + JetBrains Mono |
| `src/predict.py` | Model inference; lazy-loads tokenizer+model, int8-quantizes on CPU, max_length=256, no padding for single-sample |
| `src/autopsy.py` | Misinformation Autopsy — rhetorical-weapon classifier |
| `src/emotion.py` | Emotional trajectory curve + manipulation composite score |
| `src/who_benefits.py` | Entity → political-beneficiary mapper |
| `src/whatsapp_decode.py` | WhatsApp text normaliser + OCR |
| `src/scam_detector.py` | Indian-specific scam/phishing patterns |
| `src/fact_check.py` | Google Fact Check API helper; `rating_color()` maps rating to hex |
| `src/translator.py` | 9-script Indian-language detection + auto-translation |
| `src/train.py` | Fine-tuning script; 2 epochs, batch=4, lr=2e-5, max_length=256 |
| `src/preprocess.py` | Loads True.csv/Fake.csv → cleans → 80/10/10 split → `data/processed/` |
| `data/political_affiliations.json` | Curated entity lookup for the Who-Benefits engine; extend freely |

### Model details

- Base: `RobertaForSequenceClassification`, 125M params, vocab 50265, max position 514
- Labels: `{0: "FAKE", 1: "REAL"}`
- Trained on ISOT dataset (44K articles, primarily US political news 2016–2018)
- Fine-tuned checkpoint stored in `models/fine_tuned/` with full tokenizer files
- CPU inference: int8-quantized on load → roughly 2–3× faster than fp32

### Performance notes

The analysis pipeline parallelises the two slow steps (RoBERTa inference, Google Fact Check API) via `ThreadPoolExecutor`. All heuristic detectors (autopsy, emotion, bias, slop, scam, forward, india-boost, who-benefits) run sequentially after — together they're <50 ms.

If you're seeing slow first-paint, it's the model warmup (`_warmup_model()` in `app/app.py`) which is `@st.cache_resource`-cached; subsequent runs hit the cache.

### Data pipeline

`src/preprocess.py` expects:
- `data/raw/True.csv` and `data/raw/Fake.csv` with columns: `title`, `text`, `subject`, `date`
- Outputs train/val/test CSVs to `data/processed/` and an EDA histogram at `data/processed/eda_overview.png`

### Environment

`.env` at project root:
```
GOOGLE_FACT_CHECK_API_KEY=<your_key>
```

### Known model limitations

- Domain-biased toward US political news; lower accuracy on other domains
- Satire can trigger false positives (not labeled in ISOT dataset)
- Detects writing style, not ground-truth factual accuracy
- Hindi translation may lose nuance before inference
- The Who-Benefits engine only knows entities listed in `data/political_affiliations.json`; extend the file as needed
- Autopsy is lexicon-based — paraphrased manipulation may evade detection
