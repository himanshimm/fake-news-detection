"""
Misinformation Autopsy — rule-based rhetorical-weapon detector.

Doesn't just say "fake" — labels *which* manipulation tactic is in use:
  · fear-mongering        (existential-threat lexicon)
  · false urgency         (time-pressure verbs, deadlines)
  · cherry-picked stats   (numbers without provenance)
  · appeal to authority   (anonymous expert framing)
  · dehumanization        (slurs, animal/disease metaphors)

Public API:
    autopsy(text: str) -> list[dict]
        Each dict: {weapon, intensity (low/med/high), detail, snippets}
"""

from __future__ import annotations
import re
from typing import List, Dict


# ── 1. Lexicons ──────────────────────────────────────────────────────────────

_FEAR = [
    "destroy", "destruction", "collapse", "wipe out", "wiped out",
    "annihilate", "catastrophe", "catastrophic", "apocalypse", "doomed",
    "die", "death toll", "killed", "slaughter", "massacre",
    "horror", "horrific", "terrifying", "nightmare", "devastating",
    "end of", "extinction", "wipe us out", "obliterate",
]

_URGENCY = [
    "act now", "act fast", "immediately", "right now",
    "before it's too late", "before it is too late",
    "running out of time", "last chance", "final warning",
    "deadline", "by tomorrow", "before midnight", "expires today",
    "share before", "forward before",
    "limited time", "hurry", "don't wait", "do not wait",
]

_AUTHORITY = [
    "scientists say", "scientists confirm", "studies show",
    "research shows", "experts agree", "experts warn",
    "doctors recommend", "doctors warn", "doctor says",
    "officials confirm", "official sources say",
    "insider sources", "according to insiders",
    "leaked documents", "anonymous source",
    "top expert", "leading expert",
]

# Dehumanization: slurs + animal/disease metaphors applied to groups.
_DEHUMAN = [
    "vermin", "rats", "cockroaches", "parasites", "leeches",
    "infestation", "infesting", "swarm of", "hordes of",
    "scum", "filth", "subhuman", "savages", "animals",
    "plague", "cancer of society", "disease",
    "invaders", "invasion",
]

# Cherry-picked stats — flagged when a % or large number appears without a sourcing cue.
_PCT_RE      = re.compile(r"\b\d{1,3}(?:\.\d+)?\s*%")
_LARGE_NUM_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{4,}\b")
_SOURCE_CUES = [
    "according to", "source:", "study by", "published in",
    "report by", "data from", "as reported by",
    "see ", "citation",
]


# ── 2. Helpers ───────────────────────────────────────────────────────────────

def _find_snippets(text: str, phrases: List[str], max_snips: int = 3) -> List[str]:
    lower = text.lower()
    hits: List[str] = []
    for p in phrases:
        idx = lower.find(p)
        if idx == -1:
            continue
        # 30 chars of context on each side
        start = max(0, idx - 30)
        end   = min(len(text), idx + len(p) + 30)
        snip = text[start:end].replace("\n", " ").strip()
        if start > 0:
            snip = "…" + snip
        if end < len(text):
            snip = snip + "…"
        hits.append(snip)
        if len(hits) >= max_snips:
            break
    return hits


def _intensity(n_hits: int, low: int = 1, high: int = 3) -> str:
    if n_hits >= high:
        return "high"
    if n_hits >= low:
        return "med"
    return "low"


# ── 3. Detectors ─────────────────────────────────────────────────────────────

def _fear_mongering(text: str) -> Dict | None:
    lower = text.lower()
    hits = [w for w in _FEAR if w in lower]
    if not hits:
        return None
    return {
        "weapon":    "fear-mongering",
        "intensity": _intensity(len(hits)),
        "detail":    f"{len(hits)} existential-threat term(s): {', '.join(hits[:4])}",
        "snippets":  _find_snippets(text, hits),
    }


def _false_urgency(text: str) -> Dict | None:
    lower = text.lower()
    hits = [w for w in _URGENCY if w in lower]
    if not hits:
        return None
    return {
        "weapon":    "false urgency",
        "intensity": _intensity(len(hits)),
        "detail":    f"manufactured time pressure: {', '.join(hits[:3])}",
        "snippets":  _find_snippets(text, hits),
    }


def _appeal_to_authority(text: str) -> Dict | None:
    lower = text.lower()
    hits = [w for w in _AUTHORITY if w in lower]
    if not hits:
        return None
    # Stronger flag when "scientists/experts/doctors" appear *without* a named attribution.
    has_named_source = any(cue in lower for cue in _SOURCE_CUES)
    intensity = "high" if (len(hits) >= 2 and not has_named_source) else _intensity(len(hits))
    return {
        "weapon":    "appeal to authority",
        "intensity": intensity,
        "detail":    f"unnamed authority claims: {', '.join(hits[:3])}" + (
            "" if has_named_source else " — no named source"
        ),
        "snippets":  _find_snippets(text, hits),
    }


def _cherry_picked_stats(text: str) -> Dict | None:
    pcts  = _PCT_RE.findall(text)
    nums  = _LARGE_NUM_RE.findall(text)
    total = len(pcts) + len(nums)
    if total == 0:
        return None
    lower = text.lower()
    has_source = any(cue in lower for cue in _SOURCE_CUES)
    if has_source:
        return None  # numbers are cited — not cherry-picked
    examples = pcts[:2] + nums[:2]
    return {
        "weapon":    "cherry-picked statistics",
        "intensity": "high" if total >= 3 else "med",
        "detail":    f"{total} number(s) without provenance: {', '.join(examples)}",
        "snippets":  [],
    }


def _dehumanization(text: str) -> Dict | None:
    lower = text.lower()
    hits = [w for w in _DEHUMAN if w in lower]
    if not hits:
        return None
    return {
        "weapon":    "dehumanization",
        "intensity": "high",  # always serious
        "detail":    f"dehumanizing language: {', '.join(hits[:3])}",
        "snippets":  _find_snippets(text, hits),
    }


# ── 4. Public entry point ────────────────────────────────────────────────────

_DETECTORS = (
    _fear_mongering,
    _false_urgency,
    _appeal_to_authority,
    _cherry_picked_stats,
    _dehumanization,
)


def autopsy(text: str) -> List[Dict]:
    """Return all detected rhetorical weapons (skip weapons with no hits)."""
    if not text or not text.strip():
        return []
    findings: List[Dict] = []
    for det in _DETECTORS:
        result = det(text)
        if result is not None:
            findings.append(result)
    return findings


# ── 5. Self-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = (
        "BREAKING: Scientists confirm that 87% of all vaccines cause autism. "
        "Act now before it's too late — the deep state is hiding the truth. "
        "These globalist vermin will destroy your family if you don't share this immediately."
    )
    from pprint import pprint
    pprint(autopsy(sample))
