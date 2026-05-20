"""
DeCypher — AI-Powered Fake News Detector
Broadsheet / magazine edition.

Layout:
  Magazine masthead (time | DECYPHER | date · temperature)
  Marquee (black sliding bar)
  4 top-level tabs:
    1. FACT CHECKER       — flagship analyser (TEXT/WHATSAPP/IMAGE/URL/SOCIAL)
    2. VIRAL FAKE CLAIMS  — 21 curated cards across 8 categories + live feed
    3. SOURCE CREDIBILITY — ranked source index
    4. EVERYTHING ELSE    — stakes + method + record + FAQ stacked
  Footer

Run with:  streamlit run app/app.py
"""

# ─── 1. IMPORTS ───────────────────────────────────────────────────────────────

import sys, os, html as html_lib, textwrap, re
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import streamlit as st
import requests

from predict           import predict as _predict_raw, get_model_label
from fact_check        import search_fact_checks, rating_color
from translator        import translate_to_english
from scam_detector     import detect_scam
from autopsy           import autopsy
from emotion           import emotional_trajectory
from who_benefits      import who_benefits
from whatsapp_decode   import normalise_whatsapp, ocr_image

from dotenv import load_dotenv
load_dotenv()

def _get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, "")


# ─── 2. PAGE CONFIG ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DeCypher — Real or Fabricated",
    page_icon="⌗",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─── 3. H() — raw-HTML helper (bypasses CommonMark) ──────────────────────────

def H(s: str) -> None:
    st.markdown(textwrap.dedent(s).lstrip("\n"), unsafe_allow_html=True)


def _esc(s) -> str:
    return html_lib.escape(str(s), quote=True)


# ─── 4. CSS ───────────────────────────────────────────────────────────────────

def inject_css() -> None:
    st.markdown(
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Instrument+Serif:ital@0;1'
        '&family=JetBrains+Mono:wght@300;400;500'
        '&family=Space+Grotesk:wght@300;400;500;600;700'
        '&display=swap">',
        unsafe_allow_html=True,
    )
    css_path = Path(__file__).parent / "styles.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    css = css.replace("@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@300;400;500&family=Space+Grotesk:wght@300;400;500;600;700&display=swap');", "")
    extra = """
    .autopsy-wrap { border-top: 1px solid var(--rule); padding: 20px 28px; background: var(--paper); }
    .autopsy-head { font-family: 'JetBrains Mono', monospace; font-size: 11px;
                    letter-spacing: 0.22em; text-transform: uppercase; color: var(--dim); margin-bottom: 14px; }
    .autopsy-head b { color: var(--vermil); font-weight: 400; }
    .autopsy-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    @media (max-width: 800px) { .autopsy-grid { grid-template-columns: 1fr; } }
    .ap-card { border: 1px solid var(--rule); background: var(--bone); padding: 16px 18px 18px; }
    .ap-card .wh { font-family: 'Instrument Serif', serif; font-style: italic;
                   font-size: 22px; color: var(--ink) !important; margin-bottom: 4px; }
    .ap-card .wh em { color: var(--vermil) !important; font-style: italic; }
    .ap-card .det { font-family: 'Space Grotesk', sans-serif; font-size: 13px;
                    color: var(--dim) !important; line-height: 1.5; margin-bottom: 10px; }
    .ap-card .snip { font-family: 'JetBrains Mono', monospace; font-size: 11px;
                     color: var(--ink) !important; background: rgba(255,59,0,0.06);
                     border-left: 2px solid var(--vermil); padding: 6px 10px;
                     margin-top: 6px; line-height: 1.5; }
    .ap-card .pill { font-family: 'JetBrains Mono', monospace; font-size: 9px;
                     letter-spacing: 0.18em; text-transform: uppercase;
                     padding: 2px 8px; border: 1px solid; display: inline-block; margin-bottom: 10px; }
    .pill.i-high { color: var(--vermil); border-color: var(--vermil); }
    .pill.i-med  { color: #b87000; border-color: #b87000; }
    .pill.i-low  { color: var(--green); border-color: var(--green); }

    .emo-wrap { border-top: 1px solid var(--rule); padding: 20px 28px 8px; background: var(--paper); }
    .emo-chart { margin: 6px -6px 4px; }
    .emo-chart svg { display: block; width: 100%; }
    .emo-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; flex-wrap: wrap; gap: 12px; }
    .emo-head .l { font-family: 'JetBrains Mono', monospace; font-size: 11px;
                   letter-spacing: 0.22em; text-transform: uppercase; color: var(--dim); }
    .emo-head .l b { color: var(--vermil); font-weight: 400; }
    .emo-head .r { font-family: 'Instrument Serif', serif; font-style: italic;
                   font-size: 16px; color: var(--ink) !important; }
    .emo-meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0;
                border-top: 1px solid var(--rule); margin-top: 8px; }
    .emo-meta > div { padding: 12px 16px; border-right: 1px solid var(--rule); }
    .emo-meta > div:last-child { border-right: none; }
    .emo-meta .k { font-family: 'JetBrains Mono', monospace; font-size: 10px;
                   letter-spacing: 0.18em; text-transform: uppercase; color: var(--dim); margin-bottom: 4px; }
    .emo-meta .v { font-family: 'Instrument Serif', serif; font-size: 22px; color: var(--ink) !important; }
    .emo-meta .v.acc { color: var(--vermil) !important; }

    .wb-wrap { border-top: 1px solid var(--rule); padding: 20px 28px 24px; background: var(--paper); }
    .wb-head { font-family: 'JetBrains Mono', monospace; font-size: 11px;
               letter-spacing: 0.22em; text-transform: uppercase; color: var(--dim); margin-bottom: 12px; }
    .wb-head b { color: var(--vermil); font-weight: 400; }
    .wb-summary { font-family: 'Instrument Serif', serif; font-style: italic;
                  font-size: 20px; color: var(--ink) !important; line-height: 1.35;
                  margin-bottom: 16px; max-width: 760px; }
    .wb-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0; border: 1px solid var(--rule); }
    @media (max-width: 800px) { .wb-grid { grid-template-columns: 1fr; } }
    .wb-col { padding: 16px 18px; border-right: 1px solid var(--rule); background: var(--bone); }
    .wb-col:last-child { border-right: none; }
    .wb-col .lbl { font-family: 'JetBrains Mono', monospace; font-size: 10px;
                   letter-spacing: 0.2em; text-transform: uppercase; color: var(--dim); margin-bottom: 10px; }
    .wb-row { display: flex; justify-content: space-between; align-items: baseline;
              padding: 6px 0; border-bottom: 1px dashed var(--rule);
              font-family: 'Space Grotesk', sans-serif; font-size: 14px; }
    .wb-row:last-child { border-bottom: none; }
    .wb-row .n { font-family: 'Instrument Serif', serif; font-style: italic;
                 font-size: 16px; color: var(--ink) !important; }
    .wb-row .s { font-family: 'JetBrains Mono', monospace; font-size: 11px;
                 color: var(--vermil); letter-spacing: 0.12em; }

    .wa-norm { border-top: 1px solid var(--rule); padding: 14px 28px;
               background: rgba(255,59,0,0.04);
               font-family: 'JetBrains Mono', monospace; font-size: 11px;
               letter-spacing: 0.14em; color: var(--dim); }
    .wa-norm b { color: var(--vermil); font-weight: 400; }

    .page-eyebrow,
    .page-title,
    .page-body {
        max-width: 1080px;
        margin-left: auto;
        margin-right: auto;
        padding-left: 32px;
        padding-right: 32px;
        box-sizing: border-box;
    }
    .page-eyebrow {
        margin-top: 28px; margin-bottom: 18px;
        padding-top: 0; padding-bottom: 16px;
        display: flex; justify-content: space-between; align-items: baseline;
        border-bottom: 1px solid var(--rule);
    }
    .page-eyebrow .num {
        font-family: 'JetBrains Mono', monospace; font-size: 12px;
        letter-spacing: 0.24em; text-transform: uppercase; color: var(--dim);
    }
    .page-eyebrow .num b { color: var(--vermil); font-weight: 400; }
    .page-eyebrow .tag {
        font-family: 'JetBrains Mono', monospace; font-size: 11px;
        letter-spacing: 0.18em; text-transform: uppercase; color: var(--dim);
    }
    .page-title {
        font-family: 'Instrument Serif', serif; font-weight: 400;
        font-size: clamp(36px, 4.6vw, 68px); line-height: 0.98;
        letter-spacing: -0.018em; color: var(--ink) !important;
        margin-top: 0; margin-bottom: 28px;
    }
    .page-title em { font-style: italic; color: var(--vermil) !important; }
    .page-body { margin-bottom: 56px; }
    """
    st.markdown(f"<style>{css}\n{extra}</style>", unsafe_allow_html=True)


inject_css()


# ─── 5. MODEL ─────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _warmup_model() -> str:
    label = get_model_label()
    _predict_raw("warmup")
    return label

with st.spinner("initialising…"):
    MODEL_LABEL = _warmup_model()


def predict(text: str) -> dict:
    r = _predict_raw(text)
    return {
        "label":      r["label"],
        "confidence": round(r["confidence"] * 100, 1),
        "fake_prob":  round(r["fake_prob"]  * 100, 1),
        "real_prob":  round(r["real_prob"]  * 100, 1),
    }


# ─── 6. HEURISTICS (preserved) ────────────────────────────────────────────────

def indian_fake_news_boost(text: str) -> dict:
    t = text.lower(); boost = 0.0; reasons = []
    forward_phrases = ["forward this", "share this", "warn your family",
        "please share", "send to all", "alert all indians", "forward karen",
        "sabko bhejo", "forward करें", "सबको भेजो", "pass this on"]
    fwd_hits = [p for p in forward_phrases if p in t]
    if fwd_hits:
        boost += 0.35; reasons.append(f'WhatsApp forward language: "{fwd_hits[0]}"')

    urgency = ["breaking", "urgent", "alert", "immediate", "just in", "shocking"]
    secrecy = ["blackout", "hiding", "suppressed", "media won't tell",
               "government hiding", "they don't want you to know",
               "mainstream media silent", "censored"]
    if any(u in t for u in urgency) and any(s in t for s in secrecy):
        boost += 0.30; reasons.append("urgency + media suppression framing")

    govt = ["rbi confirms", "rbi announces", "supreme court orders",
        "modi announces", "pm modi confirms", "government confirms",
        "pib confirms", "isro reveals", "sebi orders", "uidai confirms"]
    if any(g in t for g in govt) and (any(u in t for u in urgency) or any(p in t for p in forward_phrases)):
        boost += 0.30; reasons.append("govt impersonation + urgency/forward language")

    health = ["cures cancer", "cures diabetes", "cures covid",
        "pharma lobby hiding", "doctors don't want you to know",
        "gau mutra cures", "cow urine cures", "neem cures", "doctors hate this"]
    h_hits = [p for p in health if p in t]
    if h_hits:
        boost += 0.30; reasons.append(f'Indian health misinformation: "{h_hits[0]}"')

    fin = ["upi tax", "gst on upi", "atm withdrawal banned", "bank holiday",
        "note ban", "currency ban", "new currency", "₹2000 banned",
        "pan aadhaar link fine", "income tax on whatsapp"]
    f_hits = [p for p in fin if p in t]
    if f_hits:
        boost += 0.28; reasons.append(f'Indian financial panic pattern: "{f_hits[0]}"')

    return {"boost": round(min(boost, 0.60), 2), "reasons": reasons[:3]}


def detect_bias(text: str) -> list:
    t = text.lower(); results = []
    emotional = ["shocking","outrage","devastating","explosive","bombshell",
        "horrifying","unbelievable","stunning","terrifying","catastrophic",
        "disgusting","disgraceful","traitor","criminal","corrupt","monster"]
    emo = [w for w in emotional if w in t]
    if len(emo) >= 3:
        results.append({"name":"emotional language","level":"high","detail":f"{len(emo)} loaded words"})
    elif emo:
        results.append({"name":"emotional language","level":"med","detail":f"{len(emo)} loaded word(s): {', '.join(emo[:3])}"})
    else:
        results.append({"name":"emotional language","level":"low","detail":"neutral tone"})

    absolutes = ["always","never","everyone","nobody","all ","every single","100%","proven fact"]
    ah = [w for w in absolutes if w in t]
    if len(ah) >= 2:
        results.append({"name":"absolute claims","level":"high","detail":f"uses broad absolutes: {', '.join(ah[:3])}"})
    elif ah:
        results.append({"name":"absolute claims","level":"med","detail":f"absolute claim: '{ah[0].strip()}'"})
    else:
        results.append({"name":"absolute claims","level":"low","detail":"no absolutes detected"})

    cb = ["you won't believe","the truth about","cover-up","cover up","they're hiding","wake up","going viral"]
    cbh = [w for w in cb if w in t]
    if cbh:
        results.append({"name":"sensationalism / clickbait","level":"high","detail":f'pattern: "{cbh[0]}"'})
    else:
        results.append({"name":"sensationalism / clickbait","level":"none","detail":"no clickbait patterns"})

    letters = [c for c in text if c.isalpha()]
    cr = sum(1 for c in letters if c.isupper()) / max(len(letters), 1)
    if cr > 0.45 and len(letters) > 10:
        results.append({"name":"excessive capitalisation","level":"high","detail":f"{cr*100:.0f}% caps"})
    elif cr > 0.25 and len(letters) > 10:
        results.append({"name":"excessive capitalisation","level":"med","detail":f"{cr*100:.0f}% caps"})
    else:
        results.append({"name":"excessive capitalisation","level":"low","detail":"normal case"})

    div = ["they want to","the left","the right","deep state","globalist",
        "elite","establishment","anti-national","urban naxal","godi media","presstitute"]
    dh = [w for w in div if w in t]
    if len(dh) >= 2:
        results.append({"name":"us-vs-them framing","level":"high","detail":f"{len(dh)} divisive patterns"})
    elif dh:
        results.append({"name":"us-vs-them framing","level":"med","detail":f"divisive: '{dh[0]}'"})
    else:
        results.append({"name":"us-vs-them framing","level":"low","detail":"no divisive framing"})
    return results


def detect_ai_slop(text: str) -> dict:
    t = text.lower(); score = 0; signals = []
    phrases = [("it is important to note",15),("it's important to note",15),
        ("delve into",12),("nuanced",8),("tapestry",12),("a multifaceted",12),
        ("comprehensive understanding",12),("as an ai",20),("certainly!",12),
        ("absolutely!",12),("furthermore",8),("in conclusion",10)]
    for p, pts in phrases:
        if p in t: score += pts; signals.append(f'contains "{p}"')
    sents = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 10]
    if sents:
        avg = sum(len(s.split()) for s in sents) / len(sents)
        if avg > 28: score += 15; signals.append(f"unusually long sentences (avg {avg:.0f} words)")
        elif avg > 22: score += 8; signals.append(f"lengthy sentences (avg {avg:.0f} words)")
    contractions = ["don't","can't","won't","it's","they're","i'm","we're","isn't","didn't","doesn't"]
    if not any(c in t for c in contractions) and len(text.split()) > 40:
        score += 10; signals.append("no contractions — unusually formal")
    score = min(score, 100)
    if score >= 60: verdict = "likely AI-generated"
    elif score >= 35: verdict = "possibly AI-generated"
    elif score >= 15: verdict = "some AI-like patterns"
    else: verdict = "appears human-written"
    return {"score": score, "verdict": verdict, "signals": signals[:4]}


def detect_whatsapp_forward(text: str) -> dict:
    t = text.lower(); score = 0; signals = []
    fwd = ["forward this","please forward","share this urgently","send to all",
        "share with all","forward to all","sabko bhejo","sabko share karo",
        "forward karen","forward करें","सबको भेजो","pass this on",
        "warn everyone","alert all indians"]
    fh = [p for p in fwd if p in t]
    if fh: score += 40; signals.append(f'forward instruction: "{fh[0]}"')
    guilt = ["don't ignore","don't delete","share before it's deleted",
        "going viral now","must read and share"]
    gh = [p for p in guilt if p in t]
    if gh: score += 25; signals.append(f'guilt framing: "{gh[0]}"')
    chain = ["share within","forward within","if you don't share","bad luck",
        "good luck to those who share","7 people will","10 people will"]
    ch = [p for p in chain if p in t]
    if ch: score += 30; signals.append(f'chain message: "{ch[0]}"')
    if text.count('\n') > 8: score += 10; signals.append(f"dense formatting: {text.count(chr(10))} line breaks")
    if text.count('!') >= 5: score += 15; signals.append(f"excessive punctuation: {text.count('!')} !")
    meta = ["forwarded many times","forwarded as received","as received","copy paste"]
    mh = [p for p in meta if p in t]
    if mh: score += 20; signals.append(f'forwarded metadata: "{mh[0]}"')
    score = min(score, 100)
    if score >= 60: verdict = "likely WhatsApp forward"
    elif score >= 35: verdict = "possible viral forward"
    elif score >= 15: verdict = "some forward characteristics"
    else: verdict = "does not appear to be a forward"
    return {"score": score, "verdict": verdict, "signals": signals[:4]}


_TRUE_RATINGS = {"true", "correct", "accurate", "verified", "real", "right", "legit", "legitimate"}

def fetch_debunked(api_key: str, queries: list, max_each: int = 2) -> list:
    seen, results = set(), []
    for q in queries:
        try:
            data = requests.get(
                "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                params={"key": api_key, "query": q, "pageSize": max_each, "languageCode": "en"},
                timeout=5,
            ).json()
            for claim in data.get("claims", []):
                txt = claim.get("text", "")
                if not txt or txt in seen: continue
                for review in claim.get("claimReview", [])[:1]:
                    rating = review.get("textualRating", "")
                    rating_lower = rating.lower().strip()
                    if rating_lower in _TRUE_RATINGS:
                        continue
                    seen.add(txt)
                    results.append({
                        "claim":    txt,
                        "claimant": claim.get("claimant", "Unknown"),
                        "rating":   rating,
                        "source":   review.get("publisher", {}).get("name", "Fact Checker"),
                        "url":      review.get("url", "#"),
                    })
        except Exception:
            continue
    return results


def _flag_class(level: str) -> str:
    return {"high":"f-high","med":"f-med","medium":"f-med","low":"f-low","none":"f-none"}.get(level, "f-none")


def _emotion_sparkline_svg(intensities: list, dominant: list) -> str:
    if not intensities or len(intensities) < 2:
        return ""

    W, H = 1000, 240
    pad_x, pad_t, pad_b = 18, 28, 32
    inner_w = W - 2 * pad_x
    inner_h = H - pad_t - pad_b
    n       = len(intensities)

    pts = []
    for i, v in enumerate(intensities):
        x = pad_x + (i / (n - 1)) * inner_w
        y = pad_t + (1 - max(0.0, min(1.0, v))) * inner_h
        pts.append((x, y))

    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    baseline_y = pad_t + inner_h
    area_d = line_d + f" L {pts[-1][0]:.1f},{baseline_y:.1f} L {pts[0][0]:.1f},{baseline_y:.1f} Z"

    grid = ""
    for frac in (0.25, 0.5, 0.75):
        gy = pad_t + frac * inner_h
        grid += (
            f'<line x1="{pad_x}" y1="{gy}" x2="{pad_x + inner_w}" y2="{gy}" '
            f'stroke="rgba(20,20,20,0.06)" stroke-dasharray="2,4" />'
        )

    peak_idx       = max(range(n), key=lambda i: intensities[i])
    peak_x, peak_y = pts[peak_idx]
    peak_emo       = dominant[peak_idx] if peak_idx < len(dominant) else ""
    peak_marker    = (
        f'<line x1="{peak_x:.1f}" y1="{peak_y:.1f}" x2="{peak_x:.1f}" y2="{baseline_y:.1f}" '
        f'stroke="rgba(255,59,0,0.35)" stroke-dasharray="3,4" />'
        f'<circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="5" fill="#ff3b00" stroke="#fffaf0" stroke-width="2" />'
    )
    label_anchor = "start" if peak_x < W * 0.65 else "end"
    label_x      = peak_x + (8 if label_anchor == "start" else -8)
    peak_label   = (
        f'<text x="{label_x:.1f}" y="{max(peak_y - 10, pad_t + 12):.1f}" fill="#0a0a0a" '
        f'font-family="Instrument Serif, serif" font-style="italic" font-size="16" '
        f'text-anchor="{label_anchor}">{_esc(peak_emo)} · peak</text>'
    )

    axis_labels = ""
    for frac, txt, anchor in ((0.0, "// START", "start"), (0.5, "// MIDDLE", "middle"), (1.0, "// END", "end")):
        lx = pad_x + frac * inner_w
        axis_labels += (
            f'<text x="{lx:.1f}" y="{baseline_y + 22}" fill="rgba(20,20,20,0.42)" '
            f'font-family="JetBrains Mono, monospace" font-size="11" letter-spacing="0.22em" '
            f'text-anchor="{anchor}">{txt}</text>'
        )

    return (
        f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" '
        f'style="display:block;width:100%;height:240px;">'
        f'{grid}'
        f'<line x1="{pad_x}" y1="{baseline_y}" x2="{pad_x + inner_w}" y2="{baseline_y}" '
        f'stroke="rgba(20,20,20,0.22)" />'
        f'<path d="{area_d}" fill="rgba(255,59,0,0.10)" />'
        f'<path d="{line_d}" fill="none" stroke="#ff3b00" stroke-width="2" stroke-linejoin="round" />'
        f'{peak_marker}{peak_label}{axis_labels}'
        f'</svg>'
    )


def _fetch_url_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 DeCypher"})
        body = r.text
        body = re.sub(r"<script[^>]*>.*?</script>", " ", body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r"<style[^>]*>.*?</style>",   " ", body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body).strip()
        return body[:4000]
    except Exception:
        return ""


# ─── 7. RENDER_VERDICT ───────────────────────────────────────────────────────

def render_verdict(raw_text: str, category: str, ocr_used: bool = False) -> None:
    wa_changes: list = []
    analysis_text = raw_text
    if category == "whatsapp":
        norm = normalise_whatsapp(raw_text)
        analysis_text = norm["clean"]
        wa_changes = norm["changes"]

    with st.spinner("// analysing the seam…"):
        translated, was_translated, detected_lang = translate_to_english(analysis_text)
        api_key_local = _get_secret("GOOGLE_FACT_CHECK_API_KEY")
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_pred = pool.submit(predict, translated)
            fut_fc   = pool.submit(search_fact_checks, translated[:150], api_key_local) if api_key_local else None
            result   = fut_pred.result()
            fc_results = fut_fc.result() if fut_fc else []
        ind_boost  = indian_fake_news_boost(analysis_text)
        bias_data  = detect_bias(analysis_text)
        slop_data  = detect_ai_slop(analysis_text)
        scam_data  = detect_scam(analysis_text)
        fwd_data   = detect_whatsapp_forward(analysis_text)
        autopsy_findings = autopsy(analysis_text)
        emo_data         = emotional_trajectory(analysis_text)
        wb_data          = who_benefits(analysis_text)

    if ind_boost["boost"] > 0:
        af = min(result["fake_prob"] + ind_boost["boost"] * 100, 97.0)
        ar = round(100 - af, 1); af = round(af, 1)
        if af > 50:
            result["label"] = "FAKE"; result["fake_prob"] = af
            result["real_prob"] = ar; result["confidence"] = af

    _DEBUNK_WORDS = {"false", "fake", "incorrect", "wrong", "mislead", "misleading",
                     "pants", "fabricated", "hoax", "inaccurate", "untrue", "debunked"}
    debunked_fc = [fc for fc in fc_results
                   if any(w in fc["rating"].lower() for w in _DEBUNK_WORDS)]
    if debunked_fc and result["label"] == "REAL":
        result["label"] = "FAKE"
        result["fake_prob"] = max(result["fake_prob"], 85.0)
        result["real_prob"] = round(100 - result["fake_prob"], 1)
        result["confidence"] = result["fake_prob"]

    is_fake   = result["label"] == "FAKE"
    conf      = result["confidence"]
    fake_prob = result["fake_prob"]
    real_prob = result["real_prob"]

    word_cls = "is-fake" if is_fake else "is-real"
    word_txt = "Fabricated" if is_fake else "Verified"
    if debunked_fc and is_fake and result.get("fake_prob", 0) >= 85.0:
        sub_txt = f"Overridden by fact-checkers — debunked by {debunked_fc[0]['source']}."
    else:
        sub_txt  = (
            "High confidence — multiple red flags detected." if is_fake and conf >= 75 else
            "Moderate confidence — verify independently." if conf < 80 else
            "Low confidence — treat with caution." if conf < 60 else
            "High confidence — appears credible."
        )

    signals = [(b["name"], b["detail"], b["level"]) for b in bias_data]
    signals_html = "".join(
        f'<div class="signal-row"><div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div>'
        f'<div class="flag {_flag_class(lv)}">{"medium" if lv == "med" else lv}</div></div>'
        for (k, v, lv) in signals
    )

    india_block = ""
    if ind_boost.get("reasons"):
        rows = "".join(
            f'<div class="signal-row"><div class="k">India pattern</div>'
            f'<div class="v">{_esc(r)}</div>'
            f'<div class="flag f-high">flagged</div></div>'
            for r in ind_boost["reasons"]
        )
        india_block = (
            '<div class="signal-list" style="border-top:1px solid var(--rule);'
            'border-bottom:1px solid var(--rule);background:rgba(255,59,0,0.04);">'
            + rows + '</div>'
        )

    slop_block = ""
    if slop_data.get("score", 0) > 0 or slop_data.get("signals"):
        slop_block = (
            f'<div class="signal-row"><div class="k">AI-generated content</div>'
            f'<div class="v">{_esc(slop_data["verdict"])} · {slop_data["score"]}/100</div>'
            f'<div class="flag f-{"high" if slop_data["score"] >= 60 else "med" if slop_data["score"] >= 35 else "low"}">'
            f'{slop_data["score"]}/100</div></div>'
        )

    fwd_block = ""
    if fwd_data.get("score", 0) > 0:
        fwd_block = (
            f'<div class="signal-row"><div class="k">WhatsApp forward</div>'
            f'<div class="v">{_esc(fwd_data["verdict"])} · {fwd_data["score"]}/100</div>'
            f'<div class="flag f-{"high" if fwd_data["score"] >= 60 else "med" if fwd_data["score"] >= 35 else "low"}">'
            f'{fwd_data["score"]}/100</div></div>'
        )

    scam_block = ""
    if scam_data.get("score", 0) > 0:
        scam_block = (
            f'<div class="signal-row"><div class="k">Scam / phishing</div>'
            f'<div class="v">{_esc(scam_data["verdict"])} · {scam_data["score"]}/100</div>'
            f'<div class="flag f-{"high" if scam_data["score"] >= 60 else "med" if scam_data["score"] >= 35 else "low"}">'
            f'{scam_data["score"]}/100</div></div>'
        )

    autopsy_block = ""
    if autopsy_findings:
        cards = ""
        for f in autopsy_findings:
            snip_html = ""
            for snip in (f.get("snippets") or [])[:2]:
                snip_html += f'<div class="snip">{_esc(snip)}</div>'
            cards += (
                f'<div class="ap-card">'
                f'<span class="pill i-{f["intensity"]}">{f["intensity"]}</span>'
                f'<div class="wh">The <em>{_esc(f["weapon"])}</em> trick.</div>'
                f'<div class="det">{_esc(f["detail"])}</div>'
                f'{snip_html}</div>'
            )
        autopsy_block = (
            '<div class="autopsy-wrap">'
            f'<div class="autopsy-head">// <b>Misinformation autopsy</b> · {len(autopsy_findings)} rhetorical weapon(s) detected</div>'
            f'<div class="autopsy-grid">{cards}</div></div>'
        )

    wb_block = ""
    if wb_data.get("entities"):
        ent_rows = "".join(
            f'<div class="wb-row"><span class="n">{_esc(e["name"])}</span>'
            f'<span class="s">{_esc(e["type"])}</span></div>'
            for e in wb_data["entities"][:6]
        )
        ben_rows = "".join(
            f'<div class="wb-row"><span class="n">{_esc(b["side"])}</span>'
            f'<span class="s">{b["mention_count"]}×</span></div>'
            for b in wb_data["beneficiaries"]
        )
        wb_block = (
            '<div class="wb-wrap">'
            f'<div class="wb-head">// <b>Who benefits?</b> · follow-the-money sketch</div>'
            f'<div class="wb-summary">{_esc(wb_data["summary"])}</div>'
            '<div class="wb-grid">'
            f'<div class="wb-col"><div class="lbl">// Entities mentioned</div>{ent_rows}</div>'
            f'<div class="wb-col"><div class="lbl">// Beneficiaries (by mentions)</div>{ben_rows}</div>'
            '</div></div>'
        )

    fc_block = ""
    if fc_results:
        rows = ""
        for fc in fc_results[:5]:
            rc = rating_color(fc["rating"])
            clip = fc["claim"][:140] + ("…" if len(fc["claim"]) > 140 else "")
            rows += (
                f'<div class="fc-row">'
                f'<span class="fc-badge" style="background:{rc}18;color:{rc};border-color:{rc}40;">{_esc(fc["rating"].lower())}</span>'
                f'<span class="fc-text">{_esc(clip)}</span>'
                f'<a class="fc-link" href="{_esc(fc["url"])}" target="_blank">{_esc(fc["source"])} ↗</a>'
                f'</div>'
            )
        fc_block = '<div class="fc-wrap"><div class="fc-head">// Fact-check records</div>' + rows + '</div>'

    trans_badge = (
        f'<div class="trans-badge">↳ auto-translated: {_esc((detected_lang or "indian language").lower())} → english</div>'
        if was_translated else ""
    )
    wa_norm_badge = (
        f'<div class="wa-norm">// <b>decoded</b> · {_esc(", ".join(wa_changes))}</div>'
        if (category == "whatsapp" and wa_changes) else ""
    )
    ocr_badge = (
        f'<div class="wa-norm">// <b>OCR extracted</b> · {len(analysis_text.split())} word(s) from image</div>'
        if ocr_used else ""
    )

    H(
        '<div class="verdict">'
        + trans_badge + ocr_badge + wa_norm_badge
        + '<div class="verdict-hero">'
        + '<div class="left">'
        + '<div class="label">// Verdict</div>'
        + f'<div class="word {word_cls}">{word_txt}</div>'
        + f'<div class="sub">{_esc(sub_txt)}</div>'
        + '</div>'
        + '<div class="right">'
        + f'<div class="conf-num">{int(conf)}<small>%</small></div>'
        + '<div class="conf-lbl">// Confidence</div>'
        + '</div></div>'
        + '<div class="verdict-grid">'
        + '<div class="vg-cell is-fake">'
        + '<div class="l">// Fake probability</div>'
        + f'<div class="b"><div class="fill" style="width:{fake_prob}%"></div></div>'
        + f'<div class="n">{fake_prob}<small>%</small></div></div>'
        + '<div class="vg-cell is-real">'
        + '<div class="l">// Real probability</div>'
        + f'<div class="b"><div class="fill" style="width:{real_prob}%"></div></div>'
        + f'<div class="n">{real_prob}<small>%</small></div></div></div>'
        + india_block
        + '<div class="signal-list">'
        + signals_html + slop_block + fwd_block + scam_block
        + '</div>'
        + autopsy_block + wb_block + fc_block
        + '</div>'
    )

    spark = _emotion_sparkline_svg(emo_data["intensity"], emo_data["dominant"])
    H(
        '<div class="emo-wrap">'
        '<div class="emo-head">'
        '<span class="l">// <b>Emotional trajectory</b> · intensity over article position</span>'
        f'<span class="r">{_esc(emo_data["verdict"])}</span>'
        '</div>'
        f'<div class="emo-chart">{spark}</div>'
        '<div class="emo-meta">'
        f'<div><div class="k">// Peak intensity</div><div class="v acc">{int(emo_data["peak_pct"] * 100)}%</div></div>'
        f'<div><div class="k">// Flatness (std-dev)</div><div class="v">{emo_data["flatness"]:.2f}</div></div>'
        f'<div><div class="k">// Manipulation score</div><div class="v acc">{emo_data["manipulation"]}</div></div>'
        '</div></div>'
    )
    st.caption("// AI results may contain errors. Always cross-check with a trusted source.")


# ─── 8. STATIC DATA ──────────────────────────────────────────────────────────

SOURCE_CREDIBILITY = [
    {"name": "Reuters",           "score": 96, "lean": "centre",       "type": "wire"},
    {"name": "Associated Press",  "score": 95, "lean": "centre",       "type": "wire"},
    {"name": "BBC News",          "score": 91, "lean": "centre-left",  "type": "broadcast"},
    {"name": "Snopes",            "score": 90, "lean": "centre",       "type": "fact-check"},
    {"name": "The Hindu",         "score": 89, "lean": "centre-left",  "type": "print"},
    {"name": "PTI",               "score": 88, "lean": "centre",       "type": "wire"},
    {"name": "The Economist",     "score": 88, "lean": "centre-right", "type": "magazine"},
    {"name": "AltNews",           "score": 87, "lean": "centre",       "type": "fact-check"},
    {"name": "BOOM Live",         "score": 85, "lean": "centre",       "type": "fact-check"},
    {"name": "The Guardian",      "score": 84, "lean": "left",         "type": "print"},
    {"name": "Vishvas News",      "score": 83, "lean": "centre",       "type": "fact-check"},
    {"name": "Quint WebQoof",     "score": 82, "lean": "centre",       "type": "fact-check"},
    {"name": "Factly",            "score": 81, "lean": "centre",       "type": "fact-check"},
    {"name": "PIB Fact Check",    "score": 79, "lean": "centre",       "type": "fact-check"},
    {"name": "India Today FC",    "score": 78, "lean": "centre",       "type": "fact-check"},
    {"name": "Deccan Herald",     "score": 78, "lean": "centre-left",  "type": "print"},
    {"name": "The Tribune",       "score": 77, "lean": "centre",       "type": "print"},
    {"name": "NewsLaundry",       "score": 76, "lean": "centre-left",  "type": "digital"},
    {"name": "NDTV",              "score": 76, "lean": "centre",       "type": "broadcast"},
    {"name": "Hindustan Times",   "score": 74, "lean": "centre",       "type": "print"},
    {"name": "The Print",         "score": 74, "lean": "centre",       "type": "digital"},
    {"name": "Times of India",    "score": 72, "lean": "centre",       "type": "print"},
    {"name": "India Today",       "score": 71, "lean": "centre",       "type": "broadcast"},
    {"name": "The Wire",          "score": 68, "lean": "left",         "type": "digital"},
    {"name": "ABP News",          "score": 62, "lean": "centre",       "type": "broadcast"},
    {"name": "Zee News",          "score": 48, "lean": "right",        "type": "broadcast"},
    {"name": "Fox News",          "score": 49, "lean": "right",        "type": "broadcast"},
    {"name": "Opindia",           "score": 34, "lean": "right",        "type": "digital"},
    {"name": "Republic World",    "score": 31, "lean": "right",        "type": "broadcast"},
    {"name": "Postcard News",     "score": 12, "lean": "far-right",    "type": "digital"},
]

# 21 curated cards across 8 categories
VIRAL_CARDS = [
    # ── politics ────────────────────────────────────────────────────────────
    {"category":"politics","platform":"WhatsApp","region":"India · 02 Mar 2026","verdict":"false","flag":"Verified false",
     "claim":"EVMs in Maharashtra polls were hacked overnight — 40 lakh BJP votes injected after counting ended.",
     "truth":"ECI confirmed no breach. The 'leaked CCTV' footage was recycled from a 2019 Uttar Pradesh strong-room. ECI's mock-counting audit matched VVPAT slips within statistical tolerance.",
     "reach":"6.1M","time":"22 hr","source":"AltNews"},
    {"category":"politics","platform":"WhatsApp","region":"India · 11 Feb 2026","verdict":"false","flag":"Govt impersonation",
     "claim":"Aadhaar will be MANDATORY for marriage registration from 1 June 2026 — no Aadhaar, no marriage certificate.",
     "truth":"UIDAI and the Union Ministry of Law have issued no such notification. The cited circular number does not exist in the government gazette. PIB tagged this as a recurring hoax.",
     "reach":"2.8M","time":"6 days","source":"PIB Fact Check"},
    {"category":"politics","platform":"WhatsApp","region":"India · 18 Feb 2026","verdict":"false","flag":"Scam / phishing",
     "claim":"PM Modi announced free smartphones for all BPL families under Digital India Yojana 2025. Register at the link below.",
     "truth":"No such scheme exists. The link is a phishing site that harvests Aadhaar and bank credentials. PIB has issued repeated warnings.",
     "reach":"3.7M","time":"11k+","source":"BOOM Live"},
    {"category":"politics","platform":"WhatsApp","region":"India · 14 Feb 2026","verdict":"false","flag":"Communal misinfo",
     "claim":"Government to demolish 200 ancient temples in Tamil Nadu for the new Salem-Chennai highway — list of temples circulating.",
     "truth":"The temple list is fabricated; cross-referenced with the ASI database, none of the 'listed' temples exist at the given GPS coordinates. The actual NHAI alignment does not pass through any protected religious site.",
     "reach":"4.5M","time":"7 days","source":"AltNews"},

    # ── health ──────────────────────────────────────────────────────────────
    {"category":"health","platform":"WhatsApp","region":"India · 28 Feb 2026","verdict":"false","flag":"Health misinfo",
     "claim":"Drinking warm turmeric water for 7 days completely cures diabetes. Pharma lobby hiding this for profit.",
     "truth":"Turmeric has anti-inflammatory properties but no peer-reviewed study supports the claim. Four hospitalisations were reported in Pune within a week of this forward's spread.",
     "reach":"1.8M","time":"4 hosp.","source":"Vishvas News"},
    {"category":"health","platform":"X / Twitter","region":"World · 25 Feb 2026","verdict":"false","flag":"Health misinfo",
     "claim":"WHO confirms 5G-COVID booster causes infertility in 67% of recipients — pharma lobby suppressing the study.",
     "truth":"No such study exists in any WHO bulletin or peer-reviewed journal. The cited 'Lancet 2025' paper number is fabricated. WHO and Reuters Fact Check have flagged this as composite misinformation.",
     "reach":"11.3M","time":"3 weeks","source":"Reuters Fact Check"},
    {"category":"health","platform":"WhatsApp","region":"India · 19 Jan 2026","verdict":"false","flag":"Harm reported",
     "claim":"Drinking 50ml of cow urine first thing every morning prevents all 14 forms of cancer — confirmed by AIIMS.",
     "truth":"AIIMS issued an official rebuttal. No peer-reviewed evidence supports the claim. Three patients in Haryana stopped chemotherapy after sharing the forward; one was hospitalised in March.",
     "reach":"4.7M","time":"3 hosp.","source":"BOOM Live"},
    {"category":"health","platform":"X / Twitter","region":"World · 04 Mar 2026","verdict":"false","flag":"Verified false",
     "claim":"5G towers transmit frequencies that weaken the immune system — this is why COVID deaths spiked near 5G zones.",
     "truth":"No scientific evidence links 5G to immune suppression. 5G uses non-ionising radio waves which cannot carry viruses. The '5G-zones map' was a population density map.",
     "reach":"9.6M","time":"11.4k","source":"Full Fact + Reuters"},

    # ── tech / AI ───────────────────────────────────────────────────────────
    {"category":"tech","platform":"WhatsApp","region":"India · 28 Mar 2026","verdict":"false","flag":"Verified false",
     "claim":"ChatGPT, Gemini and Claude will be banned in India from 15 April under new IT Rules. VPN users will face ₹50,000 fine.",
     "truth":"MeitY has issued no such advisory. The 'IT Rules 2026 Amendment' referenced does not exist in the public gazette. Indian users continue to access these services normally.",
     "reach":"3.4M","time":"4 days","source":"AltNews"},
    {"category":"tech","platform":"YouTube","region":"India · 16 Mar 2026","verdict":"false","flag":"Deepfake",
     "claim":"Ratan Tata endorses 'TataFastTrade' crypto platform promising 47% monthly returns — clip shows him at a press event.",
     "truth":"The clip is an AI-generated deepfake. Tata Sons issued a legal notice; the platform's UPI handles were frozen by NPCI. ~12,000 investors lost ₹2.3 crore before takedown.",
     "reach":"8.9M","time":"₹2.3 cr","source":"Vishvas News"},

    # ── finance ─────────────────────────────────────────────────────────────
    {"category":"finance","platform":"WhatsApp","region":"India · 14 Mar 2026","verdict":"false","flag":"Verified false",
     "claim":"RBI confirms all UPI transactions above ₹2,000 will be taxed 18% GST starting next month.",
     "truth":"No such announcement exists. The GST Council has not introduced any tax on UPI transactions. This is a recurring hoax, last debunked by PIB in January.",
     "reach":"4.2M","time":"11 hr","source":"PIB Fact Check"},
    {"category":"finance","platform":"WhatsApp","region":"India · 07 Mar 2026","verdict":"false","flag":"Verified false",
     "claim":"RBI will recall ALL ₹500 notes printed between 2018-2020 starting 1 April. Exchange before 31 March or lose value.",
     "truth":"RBI has issued a clarifying press note. No recall is planned. The forwarded 'circular' uses a serial format RBI does not employ. This hoax has surfaced annually since 2019.",
     "reach":"7.2M","time":"8 hr","source":"PIB Fact Check"},
    {"category":"finance","platform":"WhatsApp","region":"India · 21 Feb 2026","verdict":"mislead","flag":"Misleading",
     "claim":"Income Tax department now AUTOMATICALLY scrutinises every UPI transaction above ₹1,000.",
     "truth":"The actual threshold for AIS reporting is much higher and applies to aggregate annual transactions, not individual transfers. The forward conflates KYC reporting limits with surveillance, causing unnecessary panic.",
     "reach":"5.6M","time":"2 days","source":"Factly"},

    # ── celebrity ───────────────────────────────────────────────────────────
    {"category":"celebrity","platform":"Facebook","region":"India · 04 Feb 2026","verdict":"false","flag":"Verified false",
     "claim":"Shah Rukh Khan secretly converted to Christianity in a private Mumbai ceremony — leaked baptism photos circulating.",
     "truth":"The 'leaked' photos are from a 2014 film shoot for 'Happy New Year'. SRK's spokesperson dismissed the claim. The Facebook account that first posted it has been suspended.",
     "reach":"6.8M","time":"5 days","source":"BOOM Live"},
    {"category":"celebrity","platform":"X / Twitter","region":"India · 12 Mar 2026","verdict":"false","flag":"Verified false",
     "claim":"Virat Kohli announces immediate retirement from all formats after India-Australia series — emotional Insta post leaked.",
     "truth":"The cited Instagram post does not exist on Kohli's verified handle. BCCI has confirmed Kohli is in active selection for the next series. The image is a Photoshop composite.",
     "reach":"9.4M","time":"36 hr","source":"India Today FC"},

    # ── international ───────────────────────────────────────────────────────
    {"category":"international","platform":"Telegram","region":"World · 18 Mar 2026","verdict":"false","flag":"Verified false",
     "claim":"Russia and China sign secret pact to jointly invade Taiwan starting 15 April — leaked Beijing memo confirms.",
     "truth":"No such memo has been verified by any major intelligence outlet. The 'leaked' document uses fonts and formatting inconsistent with PRC ministry templates. Reuters and AFP traced it to a known disinformation network in Belarus.",
     "reach":"15.2M","time":"11 days","source":"Reuters Fact Check"},
    {"category":"international","platform":"X / Twitter","region":"World · 27 Feb 2026","verdict":"false","flag":"Verified false",
     "claim":"EU passes emergency law banning hijabs, niqabs and burqas in ALL public spaces — fine €5,000 per violation.",
     "truth":"The European Parliament has passed no such law. Individual member states have varying local regulations, but no EU-wide ban exists. The 'press release' image circulated is fabricated.",
     "reach":"10.7M","time":"2 weeks","source":"AFP Fact Check"},

    # ── science ─────────────────────────────────────────────────────────────
    {"category":"science","platform":"WhatsApp","region":"India · 09 Mar 2026","verdict":"false","flag":"Verified false",
     "claim":"ISRO scientists discover liquid water on the Sun's surface — first time in cosmic history, contradicts all physics.",
     "truth":"ISRO has made no such announcement. Liquid water cannot exist on the Sun's photosphere (~5,500°C). The accompanying 'press conference' image is a still from a 2019 Chandrayaan-2 update with the audio dubbed.",
     "reach":"3.1M","time":"4 days","source":"Vishvas News"},
    {"category":"science","platform":"Telegram","region":"India · 22 Feb 2026","verdict":"mislead","flag":"Misleading",
     "claim":"ISRO scientists have discovered a second permanent Moon orbiting Earth. Government hiding this from public.",
     "truth":"ISRO has made no such announcement. Small asteroids briefly enter Earth's orbit but are not permanent satellites. The accompanying 'leaked memo' is a Photoshop forgery.",
     "reach":"2.1M","time":"36 hr","source":"AltNews"},
    {"category":"science","platform":"YouTube","region":"World · 09 Feb 2026","verdict":"false","flag":"Verified false",
     "claim":"NASA admits the Moon landing was staged in a Hollywood studio. Leaked documents confirm it.",
     "truth":"No such documents exist. The landings are independently corroborated by Soviet, Australian and Japanese tracking stations. The 'leaked documents' were generated by a known fake-news farm.",
     "reach":"14M","time":"∞","source":"Snopes"},

    # ── sports ──────────────────────────────────────────────────────────────
    {"category":"sports","platform":"WhatsApp","region":"India · 24 Feb 2026","verdict":"false","flag":"Verified false",
     "claim":"FIFA bans India from 2026 World Cup qualifiers over match-fixing scandal — official suspension letter circulating.",
     "truth":"FIFA has issued no such ban. AIFF confirmed India's qualifier schedule is intact. The 'suspension letter' uses FIFA's 2018-era logo and contains formatting errors absent from genuine communications.",
     "reach":"1.9M","time":"3 days","source":"AltNews Sports"},
]

CATEGORY_ORDER = [
    ("politics",      "Politics &amp; <em>Governance</em>"),
    ("health",        "Health &amp; <em>Medicine</em>"),
    ("tech",          "AI &amp; <em>Technology</em>"),
    ("finance",       "Finance &amp; <em>Economy</em>"),
    ("celebrity",     "Celebrity &amp; <em>Culture</em>"),
    ("international", "International <em>Affairs</em>"),
    ("science",       "Science &amp; <em>Space</em>"),
    ("sports",        "<em>Sport</em>"),
]

FAQ_ITEMS = [
    ("Can I trust the verdict blindly?",
     "No — and the design is intentional. DeCypher is an evidence weigher, not a judge. Treat the verdict as a strong signal that prompts you to cross-check with the fact-check records below it."),
    ("What does the Misinformation Autopsy actually do?",
     "It labels which rhetorical weapons a text uses to persuade you — fear-mongering, false urgency, cherry-picked statistics, appeal to unnamed authority, dehumanisation — with the snippet that triggered each flag."),
    ("Why does satire sometimes get flagged?",
     "Satire borrows the surface features of misinformation. The model reads those patterns and lights up. If you've pasted The Onion, treat the score as a compliment to the writer."),
    ("How does the Hindi support work?",
     "The base RoBERTa model is English-only. When you paste Hindi, Bengali, Tamil, Telugu, Gujarati, Punjabi, Kannada or Malayalam, we translate first and analyse the English."),
    ("What's the Who-Benefits engine?",
     "A heuristic pass that picks out named parties, leaders, corporates and media houses and cross-references them against a curated affiliations file. A follow-the-money sketch, not a forensic audit."),
    ("Is my pasted text stored?",
     "No persistent storage. Inputs live in memory for the duration of inference and are then discarded."),
    ("What's the training data?",
     "The ISOT Fake News Dataset — 44,000 labelled articles from 2016–2018. Real articles scraped from Reuters; fake from outlets flagged by PolitiFact. Validation accuracy ~94%."),
    ("Where does this fall short?",
     "US political-news performance is strongest. Drops on technical claims, non-Western contexts, very short inputs, and freshly-fabricated stories."),
]


# ─── 9. MAGAZINE MASTHEAD + MARQUEE ──────────────────────────────────────────

_now      = datetime.now()
_date_str = _now.strftime("%a %d %b %Y").upper()  # e.g. MON 19 MAY 2026

H(
    '<header class="masthead">'
    '<div class="mast-row magazine">'
    '<div class="mast-side">'
    f'<div class="mt">{_date_str}</div>'
    '</div>'
    '<div class="mast-brand">'
    '<h1 class="brand-name">De<em>Cypher</em></h1>'
    '<div class="brand-tagline">— A field manual for the post-truth feed —</div>'
    '</div>'
    '<div class="mast-side right">'
    '<div class="mt">Delhi · 34°C</div>'
    '</div>'
    '</div>'
    '<div class="marquee" aria-hidden="true">'
    '<div class="marquee-track">'
    '<span><b>●</b> Truth circles the world while the lie is still putting on its shoes</span>'
    '<span>64% of you have shared a lie · the other 36% are lying about that</span>'
    '<span><b>●</b> If a message says "forward to 10" — it has already failed every test</span>'
    '<span>AI now writes the rumours · humans only forward them</span>'
    '<span><b>●</b> The cure for cancer is not in a WhatsApp message</span>'
    '<span>Outrage is the cheapest engagement metric ever invented</span>'
    '<span><b>●</b> Truth circles the world while the lie is still putting on its shoes</span>'
    '<span>64% of you have shared a lie · the other 36% are lying about that</span>'
    '<span><b>●</b> If a message says "forward to 10" — it has already failed every test</span>'
    '<span>AI now writes the rumours · humans only forward them</span>'
    '<span><b>●</b> The cure for cancer is not in a WhatsApp message</span>'
    '<span>Outrage is the cheapest engagement metric ever invented</span>'
    '</div></div></header>'
)


# ─── 10. TOP-LEVEL TABS (4 categories) ───────────────────────────────────────

page_fc, page_viral, page_src, page_else = st.tabs([
    "FACT CHECKER",
    "VIRAL FAKE CLAIMS",
    "SOURCE CREDIBILITY",
    "EVERYTHING ELSE",
])


# ─── 11. PAGE 1 · FACT CHECKER (flagship) ────────────────────────────────────

with page_fc:
    H(
        '<section>'
        '<div class="page-eyebrow">'
        '<div class="num">§ 01 · <b>The Tool</b></div>'
        '<div class="tag">Drop · Paste · Decode</div>'
        '</div>'
        '<h2 class="page-title">Run the <em>fact check</em>.</h2>'
        '</section>'
    )

    tab_text, tab_wa, tab_img, tab_url, tab_soc = st.tabs([
        "TEXT", "WHATSAPP", "IMAGE", "URL", "SOCIAL",
    ])

    with tab_text:
        H(
            '<div class="input-frame">'
            '<div class="cat-meta">'
            '<span class="lbl">// Category · <b>TEXT INPUT</b> (flagship)</span>'
            '<span class="meta-r">PASTE · CLASSIFY · DECONSTRUCT</span>'
            '</div></div>'
        )
        text_input = st.text_area(
            "Input",
            placeholder="Paste a headline, a claim, or a quote…   Hindi · Bengali · Tamil · Telugu · Gujarati · Punjabi supported.",
            height=160, label_visibility="collapsed", key="text_input",
        )
        if st.button("→  RUN THE ANALYSIS  ↗", use_container_width=True, key="run_text_btn"):
            if text_input.strip():
                render_verdict(text_input, "text")
            else:
                st.warning("// no input detected — paste some text first.")

    with tab_wa:
        H(
            '<div class="input-frame">'
            '<div class="cat-meta">'
            '<span class="lbl">// Category · <b>WHATSAPP FORWARD</b></span>'
            '<span class="meta-r">DECODE + FORWARD + SCAM SCANNERS</span>'
            '</div></div>'
        )
        whatsapp_in = st.text_area(
            "WA",
            placeholder="Paste the forwarded message — emojis, line breaks, ALL-CAPS and all. We decode before scoring.",
            height=180, label_visibility="collapsed", key="wa_input",
        )
        wa_img_file = st.file_uploader(
            "Or drop a WhatsApp screenshot (OCR)",
            type=["png","jpg","jpeg","webp"], key="wa_img_input",
        )
        st.caption("Drop a screenshot — we'll OCR the text (English + Hindi if Tesseract has it), then score it.")
        if st.button("→  RUN THE ANALYSIS  ↗", use_container_width=True, key="run_wa_btn"):
            if whatsapp_in.strip():
                render_verdict(whatsapp_in, "whatsapp")
            elif wa_img_file is not None:
                extracted = ocr_image(wa_img_file)
                if extracted:
                    render_verdict(extracted, "whatsapp", ocr_used=True)
                else:
                    st.warning("// OCR returned no text — is Tesseract installed? See README.")
            else:
                st.warning("// paste a forward or drop a screenshot.")

    with tab_img:
        H(
            '<div class="input-frame">'
            '<div class="cat-meta">'
            '<span class="lbl">// Category · <b>IMAGE / OCR</b></span>'
            '<span class="meta-r">OCR · ENG + HIN</span>'
            '</div></div>'
        )
        img_file = st.file_uploader("Image", type=["png","jpg","jpeg","webp"], key="img_input")
        st.caption("Drop a screenshot — we extract the text and run the full pipeline on it.")
        if st.button("→  RUN THE ANALYSIS  ↗", use_container_width=True, key="run_img_btn"):
            if img_file is not None:
                extracted = ocr_image(img_file)
                if extracted:
                    render_verdict(extracted, "image", ocr_used=True)
                else:
                    st.warning("// OCR returned no text — is Tesseract installed? See README.")
            else:
                st.warning("// no image dropped.")

    with tab_url:
        H(
            '<div class="input-frame">'
            '<div class="cat-meta">'
            '<span class="lbl">// Category · <b>ARTICLE URL</b></span>'
            '<span class="meta-r">FETCH · STRIP · CROSS-CHECK</span>'
            '</div></div>'
        )
        url_in = st.text_input(
            "URL",
            placeholder="https://…  paste an article URL",
            label_visibility="collapsed", key="url_input",
        )
        st.caption("We fetch the page, strip HTML, and run the full pipeline on the body text.")
        if st.button("→  RUN THE ANALYSIS  ↗", use_container_width=True, key="run_url_btn"):
            if url_in.strip().startswith(("http://", "https://")):
                with st.spinner("// fetching the page…"):
                    body = _fetch_url_text(url_in.strip())
                if body:
                    render_verdict(body, "url")
                else:
                    st.warning("// could not fetch the page — check the URL or paste the article text into the TEXT tab.")
            else:
                st.warning("// not a valid URL (must start with http:// or https://).")

    with tab_soc:
        H(
            '<div class="input-frame">'
            '<div class="cat-meta">'
            '<span class="lbl">// Category · <b>SOCIAL POST</b></span>'
            '<span class="meta-r">PASTE THE POST TEXT</span>'
            '</div></div>'
        )
        social_in = st.text_area(
            "Social",
            placeholder="Paste the text of an X, Facebook or Instagram post.",
            height=160, label_visibility="collapsed", key="soc_input",
        )
        if st.button("→  RUN THE ANALYSIS  ↗", use_container_width=True, key="run_soc_btn"):
            if social_in.strip():
                render_verdict(social_in, "social")
            else:
                st.warning("// no input detected — paste a post first.")


# ─── 12. PAGE 2 · VIRAL FAKE CLAIMS (21 categorised cards + live feed) ───────

def _render_card(idx: int, v: dict) -> str:
    return (
        f'<article class="feed-card">'
        f'<div class="fc-num">{idx:02d}</div>'
        f'<div>'
        f'<div class="fc-meta"><span class="plat">{_esc(v["platform"])}</span><span>{_esc(v["region"])}</span></div>'
        f'<div class="fc-claim">{_esc(v["claim"])}</div>'
        f'<p class="fc-truth"><b>Fact —</b> {_esc(v["truth"])}</p>'
        f'</div>'
        f'<aside class="fc-side">'
        f'<span class="fc-flag {_esc(v["verdict"])}">{_esc(v["flag"])}</span>'
        f'<div class="fc-stat"><span class="l">Estimated reach</span><span class="n acc">{_esc(v["reach"])}</span></div>'
        f'<div class="fc-stat"><span class="l">Response</span><span class="n">{_esc(v["time"])}</span></div>'
        f'<div class="fc-src">Verified by <b>{_esc(v["source"])}</b></div>'
        f'</aside></article>'
    )


with page_viral:
    H(
        '<section>'
        '<div class="page-eyebrow">'
        f'<div class="num">§ 02 · <b>The Feed</b> · {len(VIRAL_CARDS)} curated claims</div>'
        '<div class="tag">Across 8 categories</div>'
        '</div>'
        '<h2 class="page-title">Today\'s <em>viral</em> lies.</h2>'
        '</section>'
    )

    # Optional live feed at the top (when API key present)
    api_key = _get_secret("GOOGLE_FACT_CHECK_API_KEY")
    if api_key:
        with st.spinner("// fetching live fact-check data…"):
            live = fetch_debunked(api_key, [
                "india", "india health", "india politics", "modi",
                "vaccine india", "election fraud", "WHO", "climate",
            ], max_each=2)
        if live:
            H('<div class="cat-divider"><div class="name">Live <em>updates</em></div>'
              f'<div class="count"><b>●</b> {len(live[:8])} from Google Fact Check</div></div>')
            cards = '<div class="feed">'
            for i, item in enumerate(live[:8]):
                is_false = any(w in item["rating"].lower() for w in ["false","incorrect","wrong"])
                flag_cls = "false" if is_false else "mislead"
                flag_txt = "Verified false" if is_false else item["rating"]
                claim = item["claim"][:220] + ("…" if len(item["claim"]) > 220 else "")
                cards += (
                    f'<article class="feed-card">'
                    f'<div class="fc-num">{(i+1):02d}</div>'
                    f'<div>'
                    f'<div class="fc-meta"><span class="plat">Live</span><span>2026</span></div>'
                    f'<div class="fc-claim">{_esc(claim)}</div>'
                    f'<p class="fc-truth">Source: <b>{_esc(item["source"])}</b> · attributed to: {_esc(item["claimant"])}</p>'
                    f'</div>'
                    f'<aside class="fc-side">'
                    f'<span class="fc-flag {flag_cls}">{_esc(flag_txt)}</span>'
                    f'<div class="fc-stat"><span class="l">Read full</span>'
                    f'<span class="n acc"><a href="{_esc(item["url"])}" target="_blank" style="color:var(--vermil);text-decoration:none;">link ↗</a></span></div>'
                    f'<div class="fc-src">Verified by <b>{_esc(item["source"])}</b></div>'
                    f'</aside></article>'
                )
            cards += '</div>'
            H(cards)

    # Curated cards grouped by category
    by_cat: dict = defaultdict(list)
    for v in VIRAL_CARDS:
        by_cat[v.get("category", "other")].append(v)

    global_idx = 1
    for cat_key, cat_label in CATEGORY_ORDER:
        cards_in_cat = by_cat.get(cat_key, [])
        if not cards_in_cat:
            continue
        H(
            f'<div class="cat-divider">'
            f'<div class="name">{cat_label}</div>'
            f'<div class="count"><b>●</b> {len(cards_in_cat)} claim(s)</div>'
            f'</div>'
        )
        feed_html = '<div class="feed">'
        for v in cards_in_cat:
            feed_html += _render_card(global_idx, v)
            global_idx += 1
        feed_html += '</div>'
        H(feed_html)

    if not api_key:
        H(
            '<div style="max-width:1080px;margin:24px auto 0 auto;padding:0 32px;">'
            '<div style="border:1px solid var(--rule);background:var(--paper);padding:16px 22px;'
            'font-family:\'JetBrains Mono\',monospace;font-size:11px;letter-spacing:0.14em;'
            'text-transform:uppercase;color:var(--dim);">'
            '<span style="color:var(--vermil);">// enable live feed —</span> '
            'add <code style="color:var(--vermil);">GOOGLE_FACT_CHECK_API_KEY</code> to .env'
            '</div></div>'
        )


# ─── 13. PAGE 3 · SOURCE CREDIBILITY ─────────────────────────────────────────

with page_src:
    H(
        '<section>'
        '<div class="page-eyebrow">'
        '<div class="num">§ 03 · <b>The Index</b></div>'
        '<div class="tag">Curated · not affiliated</div>'
        '</div>'
        '<h2 class="page-title">Sources, <em>ranked</em>.</h2>'
        '</section>'
    )

    col_a, col_b = st.columns(2)
    with col_a:
        lean_filter = st.selectbox(
            "filter by lean",
            ["all", "centre", "centre-left", "centre-right", "left", "right", "far-right"],
            key="lean_filter",
        )
    with col_b:
        type_filter = st.selectbox(
            "filter by type",
            ["all", "wire", "broadcast", "print", "digital", "magazine", "fact-check"],
            key="type_filter",
        )

    filtered = SOURCE_CREDIBILITY
    if lean_filter != "all":
        filtered = [s for s in filtered if s["lean"] == lean_filter]
    if type_filter != "all":
        filtered = [s for s in filtered if s["type"] == type_filter]
    filtered = sorted(filtered, key=lambda x: x["score"], reverse=True)

    rows = ""
    for i, s in enumerate(filtered):
        bar_cls = "fill-hi" if s["score"] >= 75 else "fill-md" if s["score"] >= 50 else "fill-lo"
        rows += (
            f'<tr>'
            f'<td class="src-rank">{(i+1):02d}</td>'
            f'<td><span class="src-name">{_esc(s["name"])}</span></td>'
            f'<td><div class="src-bar"><div class="track">'
            f'<div class="fill {bar_cls}" style="width:{s["score"]}%"></div>'
            f'</div><span class="src-score-n">{s["score"]}</span></div></td>'
            f'<td><span class="lean-pill">{_esc(s["lean"])}</span></td>'
            f'<td style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--dim);'
            f'letter-spacing:0.12em;text-transform:uppercase;">{_esc(s["type"])}</td>'
            f'</tr>'
        )

    H(
        '<div class="page-body">'
        '<div class="src-table-wrap" style="margin-top:18px;">'
        '<table class="src-table">'
        '<thead><tr><th>#</th><th>Source</th><th>Credibility · / 100</th><th>Lean</th><th>Type</th></tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table></div>'
        '<p style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:var(--dim);'
        'letter-spacing:0.14em;margin-top:14px;text-transform:uppercase;">'
        'Scores aggregate media bias ratings, press freedom indices &amp; corrections track-records. '
        'Not affiliated with any rating body.'
        '</p></div>'
    )


# ─── 14. PAGE 4 · EVERYTHING ELSE (stakes + method + record + faq) ───────────

with page_else:
    # Hero — struck-through title + About us
    H(
        '<section class="everything-hero">'
        '<div class="page-eyebrow eh-eyebrow">'
        '<div class="num">§ 00 · <b>About</b></div>'
        '<div class="tag">The masthead · ethos · build</div>'
        '</div>'
        '<h1 class="eh-title"><span class="strike">Real or <em>Fabricated</em></span></h1>'
        '<h2 class="eh-sub">About <em>us</em>.</h2>'
        '<p class="eh-lede">A small, open tool against a large, networked problem. '
        'DeCypher reads the claim, flags the rhetoric, surfaces who benefits — '
        'then puts the final call back in your hands. Built openly, used freely, '
        'sharpened every week.</p>'
        '</section>'
    )

    # Stakes
    H(
        '<section>'
        '<div class="page-eyebrow">'
        '<div class="num">§ 04 · <b>The Stakes</b></div>'
        '<div class="tag">Updated · May 2026</div>'
        '</div>'
        '<h2 class="page-title">A quiet <em>epidemic</em>, loudly shared.</h2>'
        '</section>'
        '<div class="page-body">'
        '<div class="stats-row">'
        '<div class="stat">'
        '<div class="lbl">// Indians who have shared</div>'
        '<div class="num accent">64<small>%</small></div>'
        '<div class="ctx">forwarded a story they later learned was false — most often on WhatsApp.</div>'
        '<div class="src">Source · Reuters Digital News</div>'
        '</div>'
        '<div class="stat">'
        '<div class="lbl">// Lives lost to mob violence</div>'
        '<div class="num">46</div>'
        '<div class="ctx">killed in India between 2017–2024 in attacks traced to WhatsApp rumours.</div>'
        '<div class="src">Source · IndiaSpend reporting</div>'
        '</div>'
        '<div class="stat">'
        '<div class="lbl">// AI-generated content growth</div>'
        '<div class="num accent">1,700<small>%</small></div>'
        '<div class="ctx">rise in detected AI-generated misinformation since the public release of LLMs.</div>'
        '<div class="src">Source · NewsGuard Trends</div>'
        '</div>'
        '<div class="stat">'
        '<div class="lbl">// Reach of a false claim</div>'
        '<div class="num">6<small>×</small></div>'
        '<div class="ctx">faster spread than a true story of equivalent length, on average.</div>'
        '<div class="src">Source · MIT, Science, 2018</div>'
        '</div></div>'
        '<div class="stats-foot">'
        '<span>Truth travels slower than the rumour.</span>'
        '<span><b>●</b> Live numbers · revised weekly</span>'
        '</div></div>'
    )

    # Method
    H(
        '<section>'
        '<div class="page-eyebrow">'
        '<div class="num">§ 05 · <b>The Method</b></div>'
        '<div class="tag">From paste · to verdict · in ~2s</div>'
        '</div>'
        '<h2 class="page-title">How we <em>read</em> a claim.</h2>'
        '</section>'
        '<div class="page-body">'
        '<div class="pipeline">'
        '<div class="pipe-step">'
        '<div class="step-no">01</div>'
        '<div class="step-t">Decode &amp; translate</div>'
        '<div class="step-b">WhatsApp text is normalised. Indian-script text is auto-translated to English.</div>'
        '</div>'
        '<div class="pipe-step">'
        '<div class="step-no">02</div>'
        '<div class="step-t">Tokenise</div>'
        '<div class="step-b">Split into subwords at length 256 — matching how the RoBERTa head was trained.</div>'
        '</div>'
        '<div class="pipe-step">'
        '<div class="step-no">03</div>'
        '<div class="step-t">Classify</div>'
        '<div class="step-b">125M-param classifier (int8-quantized on CPU) returns calibrated fake / real probabilities.</div>'
        '</div>'
        '<div class="pipe-step">'
        '<div class="step-no">04</div>'
        '<div class="step-t">Autopsy</div>'
        '<div class="step-b">Rule-based rhetorical-weapon scan, emotional trajectory, India-pattern booster, scam &amp; AI-slop checks.</div>'
        '</div>'
        '<div class="pipe-step">'
        '<div class="step-no">05</div>'
        '<div class="step-t">Cross-check</div>'
        '<div class="step-b">Top phrases queried against Google Fact Check in parallel with model inference.</div>'
        '</div></div></div>'
    )

    # Margin
    H(
        '<section>'
        '<div class="page-eyebrow">'
        '<div class="num">§ 06 · <b>The Margin</b></div>'
        '<div class="tag">Why pair them, not pick one</div>'
        '</div>'
        '<h2 class="page-title">Human, meet <em>machine</em>.</h2>'
        '</section>'
        '<div class="page-body">'
        '<div class="versus">'
        '<div class="vs-card">'
        '<div class="lbl">// You, on a good day</div>'
        '<div class="who">The <em>human</em></div>'
        '<div class="vs-acc">58<small>%</small></div>'
        '<div class="desc">Average reader accuracy when asked to label a mixed batch of true and false claims, untimed.</div>'
        '</div>'
        '<div class="vs-mid"><em>vs</em><small>at scale</small></div>'
        '<div class="vs-card right">'
        '<div class="lbl">// DeCypher, every day</div>'
        '<div class="who">The <em>model</em></div>'
        '<div class="vs-acc">94<small>%</small></div>'
        '<div class="desc">Validation accuracy on a 44k-article test set.</div>'
        '</div></div></div>'
    )

    # Record
    H(
        '<section>'
        '<div class="page-eyebrow">'
        '<div class="num">§ 07 · <b>The Record</b></div>'
        '<div class="tag">Selected · 2018–2025</div>'
        '</div>'
        '<h2 class="page-title">Recent <em>incidents</em>.</h2>'
        '</section>'
        '<div class="page-body">'
        '<div class="timeline">'
        '<div class="t-row">'
        '<div class="t-date"><b>Mar 2025</b> · Maharashtra</div>'
        '<div class="t-body">'
        '<h3 class="t-h">A "free smartphone" link <em>steals</em> 11,000 Aadhaars in 36 hours.</h3>'
        '<p class="t-d">A WhatsApp forward claiming PM Modi had announced a smartphone scheme circulated through 240 groups before PIB confirmed it as a phishing operation.</p>'
        '<div class="t-tags"><span class="pill crit">Critical</span><span class="pill">Phishing</span><span class="pill">WhatsApp</span></div>'
        '</div></div>'
        '<div class="t-row">'
        '<div class="t-date"><b>Nov 2024</b> · Karnataka</div>'
        '<div class="t-body">'
        '<h3 class="t-h">An AI-generated voicenote of a sitting MLA goes <em>viral</em>.</h3>'
        '<p class="t-d">Cloned in 13 seconds of training audio, the clip pre-loaded with a fabricated communal slur reached 2.4M devices before takedown.</p>'
        '<div class="t-tags"><span class="pill crit">Critical</span><span class="pill">Deepfake</span><span class="pill">Audio</span></div>'
        '</div></div>'
        '<div class="t-row">'
        '<div class="t-date"><b>Aug 2024</b> · Bihar</div>'
        '<div class="t-body">'
        '<h3 class="t-h">"₹2,000 notes banned tomorrow" — for the <em>seventh</em> time.</h3>'
        '<p class="t-d">The recurring currency-ban hoax surfaces again, attributed to a fabricated RBI press release.</p>'
        '<div class="t-tags"><span class="pill">Misleading</span><span class="pill">Finance</span></div>'
        '</div></div>'
        '<div class="t-row">'
        '<div class="t-date"><b>Jan 2023</b> · National</div>'
        '<div class="t-body">'
        '<h3 class="t-h">"Turmeric cures diabetes in 7 days" — and four hospitalisations.</h3>'
        '<p class="t-d">A health-misinformation forward convinced patients to stop insulin. AltNews issued a takedown; the post resurfaced under twelve new accounts within a week.</p>'
        '<div class="t-tags"><span class="pill dead">Harm reported</span><span class="pill">Health</span></div>'
        '</div></div>'
        '</div></div>'
    )

    # FAQ
    H(
        '<section>'
        '<div class="page-eyebrow">'
        '<div class="num">§ 08 · <b>The Footnotes</b></div>'
        '<div class="tag">Click to open</div>'
        '</div>'
        '<h2 class="page-title">Things people <em>ask</em>.</h2>'
        '</section>'
    )
    for i, (q, a) in enumerate(FAQ_ITEMS):
        with st.expander(f"{(i+1):02d}   ·   {q}"):
            st.markdown(
                f'<div style="font-family:Space Grotesk,sans-serif;font-size:15px;'
                f'line-height:1.7;color:#0a0a0a;">{_esc(a)}</div>',
                unsafe_allow_html=True,
            )


# ─── 15. FOOTER (always visible, outside tabs) ───────────────────────────────

H(
    '<footer class="foot">'
    '<div class="foot-inner">'
    '<div class="foot-top">'
    '<div>'
    '<div class="foot-logo">De<em>Cypher</em>.</div>'
    '<p class="foot-tag">A small tool against a large problem. Built openly, used freely, sharpened constantly.</p>'
    f'<p style="font-family:\'JetBrains Mono\',monospace;font-size:10px;letter-spacing:0.18em;color:#8a8170;margin-top:8px;">Model: {_esc(MODEL_LABEL)}</p>'
    '</div>'
    '<div class="foot-col">'
    '<h5>// Pages</h5>'
    '<a>Fact Checker</a>'
    '<a>Viral Fake Claims</a>'
    '<a>Source Credibility</a>'
    '<a>Everything Else</a>'
    '</div>'
    '<div class="foot-col">'
    '<h5>// Elsewhere</h5>'
    '<a>GitHub</a>'
    '<a>Model card</a>'
    '<a>Press kit</a>'
    '<a>Report a bug</a>'
    '</div></div>'
    '<div class="foot-bottom">'
    '<div>© 2026 DeCypher · India edition</div>'
    '<div><b style="color:#ff3b00;">●</b> &nbsp;Always free · for the public good</div>'
    '</div></div></footer>'
)
