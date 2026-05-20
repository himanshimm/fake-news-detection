"""
Emotional Manipulation Score — sliding-window emotion intensity.

Compact NRC-style lexicon. Slides a window across the article and computes
emotional intensity per window, producing a curve. Real journalism is
roughly flat; propaganda has engineered peaks.

Public API:
    emotional_trajectory(text: str, n_buckets: int = 24) -> dict
        {
          buckets:       [int],          # 0..n_buckets-1
          intensity:     [float],        # normalised 0..1 per bucket
          dominant:      [str],          # dominant emotion per bucket
          peak_pct:      float,          # 0..1 peak intensity
          flatness:      float,          # std-dev; low = flat = journalistic
          manipulation:  int,            # 0..100 composite score
          verdict:       str,
        }
"""

from __future__ import annotations
import re
from collections import Counter
from statistics import pstdev
from typing import Dict, List


# ── 1. Lexicon (NRC-lite) ────────────────────────────────────────────────────
# Keep small but covering — enough to produce a meaningful curve on news text.

_LEX: Dict[str, List[str]] = {
    "fear": [
        "afraid", "scared", "terror", "terrified", "panic", "horror",
        "dread", "danger", "threat", "menace", "alarm", "fear",
        "doom", "catastrophe", "disaster", "crisis", "warning",
        "deadly", "fatal", "killed", "attack",
    ],
    "anger": [
        "angry", "outrage", "fury", "furious", "rage", "hatred",
        "betrayal", "treason", "traitor", "criminal", "corrupt",
        "scandal", "disgrace", "shameful", "violation",
    ],
    "disgust": [
        "disgust", "disgusting", "vile", "filthy", "filth", "scum",
        "revolting", "appalling", "sickening", "repulsive",
        "depraved", "shameless",
    ],
    "sadness": [
        "tragedy", "tragic", "grief", "mourning", "loss", "victim",
        "suffering", "tears", "weeping", "devastated", "heartbreak",
    ],
    "joy": [
        "joy", "happy", "celebration", "triumph", "victory",
        "success", "winning", "delight", "wonderful", "excellent",
    ],
    "surprise": [
        "shocking", "stunning", "astonishing", "unbelievable",
        "incredible", "bombshell", "explosive", "revealed",
        "exposed", "breakthrough",
    ],
    "trust": [
        "honest", "trusted", "reliable", "credible", "verified",
        "confirmed", "transparent", "official",
    ],
    "anticipation": [
        "soon", "imminent", "upcoming", "tomorrow", "next",
        "ready", "about to", "preparing",
    ],
}

# Reverse map for O(1) lookup
_WORD_TO_EMOTION: Dict[str, str] = {
    word: emo for emo, words in _LEX.items() for word in words
}


# ── 2. Tokeniser ─────────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[A-Za-z']+")


def _tokens(text: str) -> List[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


# ── 3. Public function ───────────────────────────────────────────────────────

def emotional_trajectory(text: str, n_buckets: int = 24) -> Dict:
    toks = _tokens(text)
    n = len(toks)
    if n < 20:
        # too short for a meaningful curve
        return {
            "buckets":      list(range(n_buckets)),
            "intensity":    [0.0] * n_buckets,
            "dominant":     ["—"] * n_buckets,
            "peak_pct":     0.0,
            "flatness":     0.0,
            "manipulation": 0,
            "verdict":      "input too short for trajectory analysis",
        }

    # Sliding window: each bucket is centred at an evenly-spaced token,
    # with a window wide enough to overlap its neighbours. Result: a smooth
    # curve that always spans the full text, even on short inputs.
    window_radius = max(3, n // n_buckets)
    raw_counts: List[int] = []
    dominant:   List[str] = []

    for i in range(n_buckets):
        center = (i * (n - 1)) // max(n_buckets - 1, 1)
        start  = max(0, center - window_radius)
        end    = min(n, center + window_radius + 1)
        emo_counter: Counter = Counter()
        for w in toks[start:end]:
            emo = _WORD_TO_EMOTION.get(w)
            if emo:
                emo_counter[emo] += 1
        raw_counts.append(sum(emo_counter.values()))
        dominant.append(emo_counter.most_common(1)[0][0] if emo_counter else "neutral")

    peak = max(raw_counts) or 1
    intensity = [round(c / peak, 3) for c in raw_counts]
    # True emotional-word density — sliding windows would over-count.
    density = sum(1 for w in toks if w in _WORD_TO_EMOTION) / n
    peak_pct = max(intensity)
    flatness = pstdev(intensity) if len(intensity) > 1 else 0.0

    # Composite manipulation score:
    #   high density + high peak + high std-dev = engineered emotional architecture
    score = min(
        100,
        int(density * 250 + peak_pct * 35 + flatness * 60),
    )

    if score >= 65:
        verdict = "engineered emotional architecture"
    elif score >= 35:
        verdict = "elevated emotional language"
    elif score >= 15:
        verdict = "some emotional cues"
    else:
        verdict = "flat — journalistic register"

    return {
        "buckets":      list(range(n_buckets)),
        "intensity":    intensity,
        "dominant":     dominant,
        "peak_pct":     round(peak_pct, 3),
        "flatness":     round(flatness, 3),
        "manipulation": score,
        "verdict":      verdict,
    }


# ── 4. Self-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    text = (
        "Yesterday afternoon, the council approved the new budget. "
        "Members debated for two hours before a vote of 7-3. "
        "SHOCKING betrayal! Corrupt officials have destroyed our future! "
        "Terror grips the streets as traitors plot to wipe out our heritage! "
        "Disgusting filth from these criminals will not stand!"
    )
    from pprint import pprint
    pprint(emotional_trajectory(text, n_buckets=12))
