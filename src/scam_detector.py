"""
Indian scam and phishing message detector.

Targets: UPI/payment fraud, OTP/KYC theft, lottery/prize scams,
job fraud, malicious APK installs, investment scams.
"""

import re

URL_RE = re.compile(
    r'https?://[^\s<>"\']+|www\.[^\s<>"\']+',
    re.IGNORECASE
)

_SHORTENERS = frozenset([
    'bit.ly', 'tinyurl.com', 'goo.gl', 'rb.gy', 'cutt.ly',
    'short.gy', 'ow.ly', 'tiny.cc', 'is.gd', 't.ly', 'v.gd',
])

_SCAM_TLDS = frozenset([
    '.xyz', '.top', '.click', '.win', '.loan', '.work',
    '.site', '.online', '.buzz', '.fun',
])

_IMPERSONATION_KEYWORDS = [
    'sbi-', 'hdfc-', 'icici-', 'paytm-win', 'jio-offer',
    'pm-kisan', 'pmkisan', 'modi-gift', 'government-free',
    'free-recharge', 'win-prize', 'lottery-india',
    'aadhaar-update', 'kyc-update', 'npci-reward',
]


def _score_urls(urls_raw: list, score: int, signals: list) -> int:
    for url in urls_raw[:5]:
        url_l = url.lower()
        for sh in _SHORTENERS:
            if sh in url_l:
                score += 25
                signals.append(f'shortened URL ({sh})')
                break
        for tld in _SCAM_TLDS:
            if url_l.endswith(tld) or f'{tld}/' in url_l:
                score += 20
                signals.append(f'suspicious domain extension ({tld})')
                break
        for kw in _IMPERSONATION_KEYWORDS:
            if kw in url_l:
                score += 35
                signals.append('govt/brand impersonation URL')
                break
    return score


def detect_scam(text: str) -> dict:
    """
    Returns {score: 0-100, verdict: str, signals: [str], urls_found: [str]}
    """
    t = text.lower()
    score = 0
    signals: list = []

    urls_raw = URL_RE.findall(text)
    urls_found = urls_raw[:5]
    score = _score_urls(urls_raw, score, signals)

    # OTP / KYC / account suspension fraud
    otp_patterns = [
        "share your otp", "send otp", "otp do", "otp bhejo", "enter your otp",
        "account blocked", "account suspended", "account will be blocked",
        "kyc update", "kyc verify", "update your kyc", "re-kyc",
        "link your aadhaar", "aadhaar link last date",
        "bank account freeze", "urgent kyc", "sbi kyc", "hdfc kyc",
        "paytm kyc", "upi blocked", "upi suspended",
    ]
    otp_hits = [p for p in otp_patterns if p in t]
    if otp_hits:
        score += 45
        signals.append(f'OTP/KYC fraud: "{otp_hits[0]}"')

    # Prize / lottery scams
    prize_patterns = [
        "you have won", "you are selected", "congratulations you won",
        "claim your prize", "claim your reward", "lucky draw winner",
        "lottery winner", "won ₹", "won rs.", "win ₹",
        "jio lottery", "amazon lucky draw", "bsnl lottery",
        "pm kisan award", "free mobile phone", "free recharge 730",
        "flipkart winner", "amazon winner", "you are lucky winner",
    ]
    prize_hits = [p for p in prize_patterns if p in t]
    if prize_hits:
        score += 50
        signals.append(f'prize/lottery scam: "{prize_hits[0]}"')

    # Job / work-from-home fraud
    job_patterns = [
        "work from home earn", "earn ₹ per day", "earn rs. per day",
        "daily income guarantee", "part time job online earn",
        "unlimited income from home", "data entry job earn",
        "घर बैठे कमाएं", "ghar baithe kamao",
        "registration fee required", "join now earn daily",
    ]
    job_hits = [p for p in job_patterns if p in t]
    if len(job_hits) >= 2:
        score += 40
        signals.append(f'job fraud: "{job_hits[0]}"')
    elif job_hits:
        score += 18

    # UPI / payment fraud
    upi_patterns = [
        "scan and pay to receive", "send ₹ first to get",
        "paytm me bhejo pehle", "gpay karo pehle",
        "refund process karo", "transaction pending approve",
        "minimum deposit ₹", "activation fee ₹",
        "processing fee to release", "registration charge pay",
    ]
    upi_hits = [p for p in upi_patterns if p in t]
    if upi_hits:
        score += 40
        signals.append(f'UPI/payment fraud: "{upi_hits[0]}"')

    # Malicious APK / app install
    apk_patterns = [
        "download this apk", "install this app now", "apk download link",
        "whatsapp gold download", "whatsapp plus apk",
        "new whatsapp version download", "click and install app",
    ]
    apk_hits = [p for p in apk_patterns if p in t]
    if apk_hits:
        score += 35
        signals.append(f'malicious app install: "{apk_hits[0]}"')

    # Investment / crypto scams
    invest_patterns = [
        "guaranteed return", "100% profit guaranteed", "double your money",
        "triple your investment", "risk free investment",
        "assured return daily", "bitcoin double", "crypto earn daily",
        "binary trading profit", "forex earn guaranteed",
    ]
    invest_hits = [p for p in invest_patterns if p in t]
    if invest_hits:
        score += 40
        signals.append(f'investment scam: "{invest_hits[0]}"')

    score = min(score, 100)

    if score >= 65:
        verdict = "likely scam / phishing"
    elif score >= 35:
        verdict = "suspicious — possible scam"
    elif score >= 15:
        verdict = "minor scam indicators"
    else:
        verdict = "no scam patterns detected"

    return {
        "score":      score,
        "verdict":    verdict,
        "signals":    signals[:4],
        "urls_found": urls_found,
    }
