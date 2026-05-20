"""
WhatsApp Forward Decoder — text normaliser + OCR.

Indians get most of their misinformation from WhatsApp: all-caps screaming,
emoji noise, "u r" abbreviations, Hindi-English code-switching, no punctuation.
This module normalises that chaos before the model sees it.

Public API:
    normalise_whatsapp(text: str) -> dict
        {clean: str, original: str, changes: [str]}
    ocr_image(image_file) -> str
        Streamlit UploadedFile -> extracted text (empty string on failure)
"""

from __future__ import annotations
import re
from typing import Dict, List


# ── 1. Substitution table for SMS-speak / WhatsApp shorthand ─────────────────
# Applied as whole-word replacements, case-insensitive.

_SHORTHAND = {
    r"\bu\b":           "you",
    r"\bur\b":          "your",
    r"\br\b":           "are",
    r"\bn\b":           "and",
    r"\bpls\b":         "please",
    r"\bplz\b":         "please",
    r"\bplzz+\b":       "please",
    r"\bthx\b":         "thanks",
    r"\bty\b":          "thank you",
    r"\bidk\b":         "I don't know",
    r"\bbcoz\b":        "because",
    r"\bcuz\b":         "because",
    r"\bcoz\b":         "because",
    r"\btmrw\b":        "tomorrow",
    r"\bbtw\b":         "by the way",
    r"\bwch\b":         "which",
    r"\bwt\b":          "what",
    r"\bwhn\b":         "when",
    r"\bgr8\b":         "great",
    r"\b2day\b":        "today",
    r"\b2morrow\b":     "tomorrow",
    r"\bb4\b":          "before",
    # Hinglish common
    r"\bbhai\b":        "brother",
    r"\bbhaiya\b":      "brother",
    r"\bdidi\b":        "sister",
    r"\bji\b":          "",   # honorific suffix, drop
    r"\bnahi\b":        "no",
    r"\bnahin\b":       "no",
    r"\bhaan\b":        "yes",
    r"\bha\b":          "yes",
    r"\bkya\b":         "what",
    r"\bkyun\b":        "why",
    r"\bkyon\b":        "why",
}

# Compile once
_SHORT_RE = [(re.compile(p, re.IGNORECASE), repl) for p, repl in _SHORTHAND.items()]

# Stripped wholesale: emoji & decorative Unicode in the BMP supplementary planes.
_EMOJI_RE = re.compile(
    "["                       # noqa: RUF001 — Unicode ranges
    "\U0001F300-\U0001F6FF"   # symbols & pictographs
    "\U0001F900-\U0001F9FF"   # supplemental symbols
    "\U0001FA70-\U0001FAFF"   # extended-A
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U0001F1E6-\U0001F1FF"   # flags
    "]+",
    flags=re.UNICODE,
)

_MULTI_PUNCT_RE = re.compile(r"([!?])\1{2,}")           # !!! → !
_REPEATED_CHAR_RE = re.compile(r"(.)\1{3,}")            # heyyyyy → hey
_FORWARD_DECOR_RE = re.compile(
    r"^[\s\-=*•·>]+|[\s\-=*•·>]+$", re.MULTILINE
)


def normalise_whatsapp(text: str) -> Dict:
    """Return cleaned text + log of what changed."""
    if not text:
        return {"clean": "", "original": "", "changes": []}

    original = text
    changes: List[str] = []
    out = text

    # 1. Strip emoji
    if _EMOJI_RE.search(out):
        out = _EMOJI_RE.sub(" ", out)
        changes.append("removed emoji clutter")

    # 2. Decase all-caps shouting (only if mostly caps)
    letters = [c for c in out if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.55:
        out = out.lower()
        # Re-capitalise first letter of each sentence
        out = re.sub(
            r"(^|[.!?]\s+)([a-z])",
            lambda m: m.group(1) + m.group(2).upper(),
            out,
        )
        changes.append("decased ALL-CAPS shouting")

    # 3. Expand shorthand
    expansions = 0
    for pat, repl in _SHORT_RE:
        out, n = pat.subn(repl, out)
        expansions += n
    if expansions:
        changes.append(f"expanded {expansions} shorthand/Hinglish token(s)")

    # 4. Collapse runaway punctuation + repeated letters
    if _MULTI_PUNCT_RE.search(out):
        out = _MULTI_PUNCT_RE.sub(r"\1", out)
        changes.append("collapsed runaway punctuation")
    if _REPEATED_CHAR_RE.search(out):
        out = _REPEATED_CHAR_RE.sub(r"\1\1", out)
        changes.append("trimmed elongated letters")

    # 5. Strip decorative line-borders typical of forwards
    if _FORWARD_DECOR_RE.search(out):
        out = _FORWARD_DECOR_RE.sub("", out)

    # 6. Collapse whitespace
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()

    return {"clean": out, "original": original, "changes": changes}


# ── 2. OCR (lazy import so the app still runs without Tesseract) ─────────────

def ocr_image(image_file) -> str:
    """
    Extract text from a Streamlit UploadedFile (or any file-like).
    Returns empty string if pytesseract / Tesseract isn't installed.
    """
    try:
        import pytesseract           # noqa: WPS433 — lazy import
        from PIL import Image
    except ImportError:
        return ""

    try:
        img = Image.open(image_file)
        # Hindi + English language packs if available; falls back to English only.
        try:
            text = pytesseract.image_to_string(img, lang="eng+hin")
        except pytesseract.TesseractError:
            text = pytesseract.image_to_string(img, lang="eng")
        return text.strip()
    except Exception:
        return ""


# ── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = (
        "🚨🚨🚨 BREAKING ALERT!!!!!\n"
        "MODI JI ANNOUNCED FREE PHONES FOR ALL!!!\n"
        "Pls forward to all ur contacts b4 it's deleted 🙏🙏🙏\n"
        "U r selected coz u r lucky 😱\n"
        "============"
    )
    from pprint import pprint
    pprint(normalise_whatsapp(sample))
