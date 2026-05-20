"""
"Who Benefits?" engine — heuristic political-beneficiary mapper.

Scans the input for named entities (parties, leaders, corporates, media houses)
using a curated lookup table at data/political_affiliations.json. For each
entity, reports its side / affiliation / funders so the user can see who
gains if the narrative spreads uncontested.

This is intentionally rule-based — no LLM, no live database hits, no surprises.
Quality of output scales with the curation file. Easy to extend.

Public API:
    who_benefits(text: str) -> dict
        {
          entities:     [{name, type, side, leans?, affiliation?, funders?, owner?, sector?}],
          beneficiaries: [{side, mention_count, sample_entity}],
          summary:      str,
        }
"""

from __future__ import annotations
import json
import os
from collections import Counter, defaultdict
from typing import Dict, List


_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "political_affiliations.json",
)


def _load_db() -> Dict:
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_DB = _load_db()


def _bucketed_lookup() -> List[tuple]:
    """
    Flatten the JSON into a list of (key, type_label, payload) tuples,
    sorted longest-key-first so 'narendra modi' wins over 'modi'.
    """
    flat: List[tuple] = []
    type_map = {
        "parties_india":   "party (IN)",
        "leaders_india":   "leader (IN)",
        "parties_us":      "party (US)",
        "leaders_us":      "leader (US)",
        "media_owners":    "media",
        "corporates":      "corporate",
    }
    for bucket, label in type_map.items():
        block = _DB.get(bucket, {})
        if not isinstance(block, dict):
            continue
        for key, payload in block.items():
            flat.append((key.lower(), label, payload))
    flat.sort(key=lambda t: len(t[0]), reverse=True)
    return flat


_LOOKUP = _bucketed_lookup()


def who_benefits(text: str) -> Dict:
    """
    Extract beneficiary signals from the input. Always returns a dict.
    Empty result when no entities matched.
    """
    if not text or not text.strip():
        return {"entities": [], "beneficiaries": [], "summary": "no input"}

    lower = text.lower()
    seen: set = set()
    entities: List[Dict] = []
    side_counts: Counter = Counter()
    side_samples: Dict[str, str] = {}

    for key, type_label, payload in _LOOKUP:
        if key in seen:
            continue
        if key in lower:
            seen.add(key)
            side = payload.get("side") or payload.get("affiliation") or "unaffiliated"
            entity = {
                "name":  key,
                "type":  type_label,
                "side":  side,
                **{k: v for k, v in payload.items() if k != "side"},
            }
            entities.append(entity)
            side_counts[side] += 1
            side_samples.setdefault(side, key)

    if not entities:
        return {
            "entities":      [],
            "beneficiaries": [],
            "summary":       "no recognisable political or corporate entities",
        }

    beneficiaries = [
        {
            "side":           side,
            "mention_count":  count,
            "sample_entity":  side_samples[side],
        }
        for side, count in side_counts.most_common()
    ]

    top = beneficiaries[0]
    if len(beneficiaries) == 1:
        summary = (
            f"Narrative singles out one beneficiary: {top['side']} "
            f"(via mention of '{top['sample_entity']}')."
        )
    else:
        summary = (
            f"Multiple stakeholders implicated. Top beneficiary by mentions: "
            f"{top['side']}. Cross-faction mentions can indicate framing rather than alignment."
        )

    return {
        "entities":      entities,
        "beneficiaries": beneficiaries,
        "summary":       summary,
    }


# ── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = (
        "Modi announced new electoral bond reforms today. Critics from Congress "
        "and the Aam Aadmi Party led by Kejriwal called the move opaque. "
        "Adani and Reliance executives were seen attending the announcement."
    )
    from pprint import pprint
    pprint(who_benefits(sample))
