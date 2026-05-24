from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse


NOVO_QUERY = '("Novo Nordisk" OR Ozempic OR Wegovy OR Rybelsus OR semaglutide OR "oral semaglutide")'
LILLY_QUERY = '("Eli Lilly" OR Mounjaro OR Zepbound OR tirzepatide OR orforglipron OR retatrutide)'

COMPANY_KEYWORDS = {
    "Novo Nordisk": ["novo nordisk", "ozempic", "wegovy", "rybelsus", "semaglutide", "oral semaglutide", "novo"],
    "Eli Lilly": ["eli lilly", "mounjaro", "zepbound", "tirzepatide", "orforglipron", "retatrutide", "lilly"],
}

FALSE_POSITIVE_CONTEXT = {
    "Novo Nordisk": ["ozempic", "wegovy", "rybelsus", "semaglutide", "glp-1", "obesity", "diabetes", "pharmaceutical", "pharma"],
    "Eli Lilly": ["mounjaro", "zepbound", "tirzepatide", "orforglipron", "retatrutide", "glp-1", "obesity", "diabetes", "pharmaceutical", "pharma"],
}

TOPIC_RULES = [
    ("Weight loss efficacy", ["weight loss", "lost weight", "body weight", "obesity drug", "obesity treatment", "efficacy"]),
    ("Diabetes treatment", ["diabetes", "a1c", "blood sugar", "glycemic", "type 2"]),
    ("GLP-1 market competition", ["glp-1", "market competition", "rival", "compete", "competition", "obesity market"]),
    ("Drug pricing / insurance / access", ["price", "pricing", "insurance", "coverage", "covered", "access", "medicare", "medicaid", "copay", "cost"]),
    ("Supply shortage", ["shortage", "supply", "out of stock", "availability", "demand", "capacity"]),
    ("Side effects / safety", ["side effect", "adverse", "safety", "risk", "warning", "death", "gastroparesis", "nausea"]),
    ("Cardiovascular outcomes", ["cardiovascular", "heart", "stroke", "reduced risk", "outcomes", "cvd"]),
    ("Oral GLP-1", ["oral", "pill", "tablet", "oral semaglutide", "orforglipron"]),
    ("Pipeline / next-generation drugs", ["pipeline", "next-generation", "retatrutide", "orforglipron", "cagrisema", "amycretin", "trial"]),
    ("Earnings / revenue / market share", ["earnings", "revenue", "sales", "market share", "forecast", "profit", "stock", "shares"]),
    ("Celebrity / lifestyle culture", ["celebrity", "hollywood", "lifestyle", "tiktok", "influencer", "fashion"]),
    ("Public health / obesity policy", ["public health", "obesity policy", "policy", "who", "health system", "population"]),
    ("Compounded GLP-1s", ["compound", "compounded", "compounding", "copycat"]),
    ("Legal / regulatory", ["lawsuit", "legal", "regulatory", "fda", "ema", "regulator", "approval", "approved", "patent"]),
    ("Food industry impact", ["food industry", "snack", "restaurant", "grocery", "consumer staples", "food sales"]),
]

POSITIVE_KEYWORDS = [
    "approval", "approved", "benefit", "effective", "breakthrough", "growth",
    "strong sales", "positive trial", "reduced risk", "successful",
]
NEGATIVE_KEYWORDS = [
    "lawsuit", "shortage", "adverse event", "side effect", "risk", "warning",
    "death", "denied coverage", "backlash", "safety concern",
]

SOURCE_TIERS = {
    "Tier 1": ["reuters.com", "bloomberg.com", "wsj.com", "nytimes.com", "ft.com", "cnbc.com", "apnews.com", "bbc.com", "theguardian.com", "statnews.com"],
    "Trade": ["biopharmadive.com", "fiercepharma.com", "pharmavoice.com", "endpoints.news", "pharmaceutical-technology.com", "evaluate.com", "fiercebiotech.com"],
    "Finance": ["marketwatch.com", "investors.com", "barrons.com", "finance.yahoo.com", "seekingalpha.com", "fool.com"],
}


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower() or "https", netloc, path, "", "", ""))


def source_domain(url: str, fallback: str = "") -> str:
    host = urlparse(url or "").netloc.lower().removeprefix("www.")
    return host or clean_text(fallback).lower()


def classify_source(domain: str) -> tuple[str, str, int, int]:
    domain = (domain or "").lower().removeprefix("www.")
    for tier, domains in SOURCE_TIERS.items():
        if any(domain == item or domain.endswith("." + item) for item in domains):
            if tier == "Tier 1":
                return "Tier 1", "News", 95, 100000
            if tier == "Trade":
                return "Trade", "Trade Media", 80, 35000
            return "Finance", "Finance Media", 75, 50000
    return "Other", "News", 45, 10000


def parse_date(value: str) -> str:
    raw = clean_text(value)
    if not raw:
        return datetime.now(timezone.utc).date().isoformat()
    candidates = [
        (raw[:16], "%Y%m%dT%H%M%SZ"),
        (raw[:14], "%Y%m%d%H%M%S"),
        (raw[:20], "%Y-%m-%dT%H:%M:%SZ"),
        (raw[:10], "%Y-%m-%d"),
    ]
    for candidate, fmt in candidates:
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    return raw[:10]


def matched_keywords(company: str, text: str) -> list[str]:
    haystack = text.lower()
    found = [kw for kw in COMPANY_KEYWORDS[company] if kw in haystack]
    if "novo" in found and "novo nordisk" in found:
        found.remove("novo")
    if "lilly" in found and "eli lilly" in found:
        found.remove("lilly")
    return sorted(set(found))


def passes_false_positive_controls(company: str, keywords: list[str], text: str) -> bool:
    lowered = text.lower()
    if company == "Novo Nordisk" and keywords == ["novo"]:
        return any(term in lowered for term in FALSE_POSITIVE_CONTEXT[company])
    if company == "Eli Lilly" and keywords == ["lilly"]:
        return any(term in lowered for term in FALSE_POSITIVE_CONTEXT[company])
    return bool(keywords)


def classify_topic(text: str) -> str:
    lowered = text.lower()
    for topic, words in TOPIC_RULES:
        if any(word in lowered for word in words):
            return topic
    return "Other"


def sentiment_from_text(text: str, tone: Any = None) -> tuple[str, float]:
    try:
        score = max(-1.0, min(1.0, float(tone) / 10.0))
    except (TypeError, ValueError):
        lowered = text.lower()
        pos = sum(1 for word in POSITIVE_KEYWORDS if word in lowered)
        neg = sum(1 for word in NEGATIVE_KEYWORDS if word in lowered)
        score = 0.0 if pos == neg else max(-1.0, min(1.0, (pos - neg) * 0.2))
    if score >= 0.15:
        return "Positive", round(score, 3)
    if score <= -0.15:
        return "Negative", round(score, 3)
    return "Neutral", round(score, 3)


def stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def normalize_gdelt_article(article: dict[str, Any], company: str) -> dict[str, Any] | None:
    title = clean_text(article.get("title"))
    snippet = clean_text(article.get("seendate") and article.get("snippet") or article.get("description") or article.get("summary"))
    url = normalize_url(clean_text(article.get("url")))
    domain = source_domain(url, article.get("domain") or article.get("sourceCommonName"))
    text = f"{title} {snippet} {url} {domain}"
    keywords = matched_keywords(company, text)
    if not passes_false_positive_controls(company, keywords, text):
        return None
    topic = classify_topic(text)
    sentiment, sentiment_score = sentiment_from_text(text, article.get("tone"))
    tier, channel, authority, reach = classify_source(domain)
    date = parse_date(article.get("seendate") or article.get("date") or "")
    source = clean_text(article.get("sourceCommonName") or article.get("domain") or domain or "Unknown source")
    dedupe_basis = url or f"{title.lower()}|{date}|{domain}"
    return {
        "id": stable_id(company, dedupe_basis),
        "date": date,
        "company": company,
        "matchedEntity": ", ".join(keywords[:3]) if keywords else company,
        "channel": channel,
        "source": source,
        "sourceDomain": domain,
        "sourceTier": tier,
        "title": title or "(Untitled article)",
        "snippet": snippet,
        "url": url,
        "topic": topic,
        "sentiment": sentiment,
        "sentimentScore": sentiment_score,
        "reach": reach,
        "engagement": 0,
        "sourceAuthority": authority,
        "matchedKeywords": keywords,
        "rawSource": "GDELT",
        "language": article.get("language"),
        "country": article.get("sourceCountry"),
        "isProxyMetrics": True,
        "dataQualityNotes": ["GDELT does not provide true impressions or engagement; reach and authority are rule-based proxies."],
    }


def dedupe_mentions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: (item.get("date", ""), item.get("title", "")), reverse=True):
        key = record.get("url") or f"{record.get('title', '').lower()}|{record.get('date')}|{record.get('sourceDomain')}"
        key = f"{record.get('company')}|{key}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


QUERY_DEFINITIONS = {
    "Novo Nordisk": {
        "query": NOVO_QUERY,
        "falsePositiveControls": "Standalone Novo is retained only with GLP-1, obesity, diabetes, or pharma context.",
    },
    "Eli Lilly": {
        "query": LILLY_QUERY,
        "falsePositiveControls": "Standalone Lilly is retained only with GLP-1, obesity, diabetes, or pharma context.",
    },
}
