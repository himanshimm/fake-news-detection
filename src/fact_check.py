"""
Google Fact Check Tools API helper

HOW IT WORKS:
─────────────
Google's Fact Check API searches a database of fact-checks published
by verified organizations (Snopes, PolitiFact, AFP, etc.).

We send the article's key claim → get back a list of matching fact-checks
with ratings like "False", "Mostly True", "Misleading" etc.

You need a free API key from:
https://developers.google.com/fact-check/tools/api/reference/rest
(Enable "Fact Check Tools API" in Google Cloud Console)
"""

import requests
import os


FACT_CHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


def search_fact_checks(query: str, api_key: str, max_results: int = 3) -> list:
    """
    Searches Google Fact Check API for claims matching the query text.
    Returns a list of fact-check results, or empty list if none found / no key.
    
    Each result looks like:
    {
        "claim":    "The text of the claim",
        "claimant": "Who made the claim",
        "rating":   "False / Mostly True / etc.",
        "source":   "Snopes / PolitiFact / etc.",
        "url":      "https://..."
    }
    """
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        return []   # Gracefully skip if no key provided

    # Truncate query to avoid API limits (max ~200 chars works well)
    query = query[:200]

    try:
        response = requests.get(
            FACT_CHECK_URL,
            params={
                "key":           api_key,
                "query":         query,
                "pageSize":      max_results,
                "languageCode":  "en",
            },
            timeout=5
        )

        if response.status_code != 200:
            return []

        data = response.json()
        claims = data.get("claims", [])

        results = []
        for claim in claims:
            # Each claim can have multiple reviews from different organizations
            for review in claim.get("claimReview", []):
                results.append({
                    "claim":    claim.get("text", "N/A"),
                    "claimant": claim.get("claimant", "Unknown"),
                    "rating":   review.get("textualRating", "N/A"),
                    "source":   review.get("publisher", {}).get("name", "N/A"),
                    "url":      review.get("url", "#"),
                })

        return results[:max_results]

    except Exception:
        return []   # Never crash the app if the API fails


def rating_color(rating: str) -> str:
    """Returns a color based on the rating text for UI display."""
    rating_lower = rating.lower()
    if any(w in rating_lower for w in ["false", "fake", "incorrect", "wrong", "pants"]):
        return "#FF4B4B"   # Red
    elif any(w in rating_lower for w in ["true", "correct", "accurate"]):
        return "#00C853"   # Green
    elif any(w in rating_lower for w in ["mostly", "partly", "partial", "mislead", "mixture"]):
        return "#FF9800"   # Orange
    else:
        return "#9E9E9E"   # Grey for unknown
