"""
src/predict.py
Loads fine-tuned model (if available) or falls back to pretrained RoBERTa.
Used by app/app.py for single-article inference.
"""

import os
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import logging

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FINE_TUNED_DIR = os.path.join(_BASE_DIR, "models", "fine_tuned")
_PRETRAINED     = "hamzab/roberta-fake-news-classification"

# ── Label map ─────────────────────────────────────────────────────────────────
ID2LABEL = {0: "FAKE", 1: "REAL"}

# ── Device ────────────────────────────────────────────────────────────────────
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _use_fine_tuned() -> bool:
    # Opt-in via DECYPHER_USE_FINETUNED=1. Default is the pretrained base,
    # which was trained on the full ISOT (44k); the local fine-tune is a
    # 3k-sample / 2-epoch top-up and tends to add noise rather than skill.
    if os.getenv("DECYPHER_USE_FINETUNED") != "1":
        return False
    required = ["config.json", "tokenizer_config.json"]
    return all(
        os.path.exists(os.path.join(_FINE_TUNED_DIR, f)) for f in required
    )


def load_model():
    """
    Load tokenizer + model.
    Returns (tokenizer, model, model_source_label, training_max_length).
    """
    if _use_fine_tuned():
        source = _FINE_TUNED_DIR
        label  = "fine-tuned (ISOT, opt-in)"
        train_max_length = 256
        logger.info(f"Loading fine-tuned model from {source}")
    else:
        source = _PRETRAINED
        label  = "pretrained (hamzab/roberta-fake-news-classification)"
        train_max_length = 512
        logger.info(f"Loading pretrained model: {source}")

    tokenizer = AutoTokenizer.from_pretrained(source)
    model     = AutoModelForSequenceClassification.from_pretrained(source)
    model.to(device)
    model.eval()

    # int8 dynamic quantization is opt-in only — set DECYPHER_QUANTIZE=1.
    # It's ~2-3× faster on CPU but can degrade accuracy on RoBERTa classifiers,
    # sometimes flipping predictions wholesale. Off by default for correctness.
    if device.type == "cpu" and os.getenv("DECYPHER_QUANTIZE") == "1":
        try:
            model = torch.quantization.quantize_dynamic(
                model, {nn.Linear}, dtype=torch.qint8,
            )
            label = f"{label} · int8-quantized"
        except Exception as e:
            logger.warning(f"Quantization skipped: {e}")

    return tokenizer, model, label, train_max_length


# ── Lazy globals (loaded once per session) ────────────────────────────────────
_tokenizer        = None
_model            = None
_model_label      = None
_train_max_length = 512


def _ensure_loaded():
    global _tokenizer, _model, _model_label, _train_max_length
    if _model is None:
        _tokenizer, _model, _model_label, _train_max_length = load_model()


def get_model_label() -> str:
    """Return a human-readable string describing which model is active."""
    _ensure_loaded()
    return _model_label


def predict(text: str, max_length: int | None = None) -> dict:
    """
    Run inference on a single piece of text.

    Returns:
        {
            "label":      "FAKE" | "REAL",
            "confidence": float (0–1),
            "fake_prob":  float (0–1),
            "real_prob":  float (0–1),
        }
    """
    _ensure_loaded()

    if not text or not text.strip():
        return {
            "label":      "UNKNOWN",
            "confidence": 0.0,
            "fake_prob":  0.0,
            "real_prob":  0.0,
        }

    ml = max_length if max_length is not None else _train_max_length

    encoding = _tokenizer(
        text.strip(),
        truncation=True,
        padding=False,
        max_length=ml,
        return_tensors="pt",
    )
    input_ids      = encoding["input_ids"].to(device)
    attention_mask = encoding["attention_mask"].to(device)

    with torch.inference_mode():
        outputs = _model(input_ids=input_ids, attention_mask=attention_mask)
        probs   = torch.softmax(outputs.logits, dim=-1).squeeze().cpu().tolist()

    # probs[0] = FAKE, probs[1] = REAL
    fake_prob  = round(probs[0], 4)
    real_prob  = round(probs[1], 4)
    pred_idx   = int(torch.argmax(torch.tensor(probs)).item())
    label      = ID2LABEL[pred_idx]
    confidence = round(max(probs), 4)

    return {
        "label":      label,
        "confidence": confidence,
        "fake_prob":  fake_prob,
        "real_prob":  real_prob,
    }


# ── Quick self-test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    samples = [
        "Scientists confirm the Earth is 4.5 billion years old based on radiometric dating.",
        "BREAKING: Government puts microchips in COVID vaccines to track citizens worldwide.",
        "The Federal Reserve raised interest rates by 25 basis points at today's meeting.",
        "Aliens have landed in Nevada and the government is hiding the truth from you.",
    ]

    print(f"\nActive model: {get_model_label()}\n")
    print("-" * 65)

    for text in samples:
        result = predict(text)
        bar_fake = "█" * int(result["fake_prob"] * 20)
        bar_real = "█" * int(result["real_prob"] * 20)
        print(f"Text    : {text[:70]}…" if len(text) > 70 else f"Text    : {text}")
        print(f"Label   : {result['label']}  ({result['confidence']*100:.1f}% confident)")
        print(f"FAKE    : {bar_fake:<20} {result['fake_prob']*100:.1f}%")
        print(f"REAL    : {bar_real:<20} {result['real_prob']*100:.1f}%")
        print("-" * 65)
