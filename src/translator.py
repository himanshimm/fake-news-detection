"""
Multi-script Indian language detector and English translator.

Supports: Hindi/Marathi (Devanagari), Bengali, Punjabi (Gurmukhi),
Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam.
"""

from deep_translator import GoogleTranslator
import re

# (unicode range, lang_code, display_name)
_SCRIPT_RANGES = [
    (r'[ऀ-ॿ]', 'hi', 'Hindi/Marathi'),
    (r'[ঀ-৿]', 'bn', 'Bengali'),
    (r'[਀-੿]', 'pa', 'Punjabi'),
    (r'[઀-૿]', 'gu', 'Gujarati'),
    (r'[଀-୿]', 'or', 'Odia'),
    (r'[஀-௿]', 'ta', 'Tamil'),
    (r'[ఀ-౿]', 'te', 'Telugu'),
    (r'[ಀ-೿]', 'kn', 'Kannada'),
    (r'[ഀ-ൿ]', 'ml', 'Malayalam'),
]

_COMPILED = [(re.compile(p), code, name) for p, code, name in _SCRIPT_RANGES]


def detect_indian_script(text: str) -> tuple:
    """Returns (lang_code, display_name) of dominant Indian script, or ('', '')."""
    best_code, best_name, best_count = '', '', 0
    for pattern, code, name in _COMPILED:
        count = len(pattern.findall(text))
        if count > best_count:
            best_code, best_name, best_count = code, name, count
    if best_count / max(len(text), 1) > 0.08:
        return best_code, best_name
    return '', ''


def translate_to_english(text: str) -> tuple:
    """
    Translates to English if an Indian script is detected.
    Returns (translated_text, was_translated, source_language_name).
    """
    lang_code, lang_name = detect_indian_script(text)
    if not lang_code:
        return text, False, ''
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return translated, True, lang_name
    except Exception:
        return text, False, ''


def is_hindi(text: str) -> bool:
    code, _ = detect_indian_script(text)
    return bool(code)
