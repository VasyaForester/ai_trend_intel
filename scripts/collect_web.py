"""Collect AI security trend data from public RSS/Atom and HTML sources.

This collector does not use search APIs. It reads configured public sources,
tries RSS/Atom discovery first, falls back to lightweight HTML scraping, matches
items against config/keywords.json, and writes ui/data.json for the dashboard.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS_PATH = ROOT / "config" / "keywords.json"
KEY_DOCUMENTS_PATH = ROOT / "config" / "key_documents.json"
SEARCH_SOURCES_PATH = ROOT / "config" / "search_sources.json"
OUTPUT_PATH = ROOT / "ui" / "data.json"

WINDOW_WEEKS = 12
PALETTE = ["#22d3ee", "#a855f7", "#60a5fa", "#f59e0b", "#34d399", "#f472b6", "#facc15"]
USER_AGENT = "ai-trend-intel/1.0 (public RSS and HTML research)"

AUTHORITY_DOMAINS = {
    "owasp.org": 5.0,
    "genai.owasp.org": 5.0,
    "cloudsecurityalliance.org": 4.7,
    "labs.cloudsecurityalliance.org": 4.7,
    "openai.com": 4.2,
    "anthropic.com": 4.2,
    "deepmind.google": 4.2,
    "blog.google": 4.0,
    "googleblog.com": 4.0,
    "security.googleblog.com": 4.0,
    "google.com": 3.8,
    "microsoft.com": 3.8,
    "aws.amazon.com": 3.7,
    "ibm.com": 3.5,
    "nvidia.com": 3.5,
    "meta.com": 3.4,
    "ai.meta.com": 3.4,
    "apple.com": 3.2,
    "nist.gov": 4.3,
    "mitre.org": 4.0,
    "atlas.mitre.org": 4.0,
}

GENERIC_DASHBOARD_QUERIES = {
    "ai security",
    "llm security",
    "genai security",
    "generative ai security",
    "ai cybersecurity",
    "ml security",
    "machine learning security",
    "ai attack",
    "llm attack",
    "genai attack",
    "ai vulnerability",
    "llm vulnerability",
    "genai vulnerability",
    "ai exploit",
    "ai cve",
    "llm cve",
    "genai cve",
    "agentic ai security",
    "agentic security",
    "ai security framework",
    "ai security benchmark",
    "llm security benchmark",
    "mitre atlas",
    "owasp llm",
    "owasp top 10 for llm applications",
    "owasp top 10 llm",
    "owasp agentic",
    "owasp agentic ai",
    "nist ai rmf",
    "iso 42001",
    "ai risk management framework",
}

TREND_FOCUS_QUERIES = {
    "self-evolving agent",
    "model context protocol",
    "mcp security",
    "mcp attack",
    "mcp vulnerability",
    "agentic skill",
    "agentic skills",
    "agent skill",
    "agent skills",
    "agent memory",
    "agentic workflow",
    "autonomous agent",
    "prompt injection",
    "indirect prompt injection",
    "prompt attack",
    "llm guardrails",
    "dynamic guardrails",
    "llm firewall",
    "tool poisoning",
    "function calling abuse",
    "tool abuse",
    "agent hijacking",
    "agent privilege escalation",
    "ai red teaming",
    "rag poisoning",
    "context window overflow",
    "data exfiltration via llm",
}

RSS_HINTS = (
    "feed",
    "rss",
    "rss.xml",
    "atom.xml",
    "feed.xml",
)


@dataclass
class Source:
    url: str
    category: str


@dataclass
class Item:
    title: str
    url: str
    summary: str
    source_url: str
    source_host: str
    published: datetime | None = None


class SourceHTMLParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.meta_description = ""
        self.feed_links: set[str] = set()
        self.links: list[tuple[str, str]] = []
        self.times: list[str] = []
        self._in_title = False
        self._active_href: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            if name in {"description", "og:description", "twitter:description"} and attrs_dict.get("content"):
                self.meta_description = attrs_dict["content"].strip()
        elif tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            typ = attrs_dict.get("type", "").lower()
            href = attrs_dict.get("href", "")
            if href and ("alternate" in rel or "feed" in rel) and ("rss" in typ or "atom" in typ or "xml" in typ):
                self.feed_links.add(urljoin(self.base_url, href))
        elif tag == "a":
            href = attrs_dict.get("href", "")
            if href:
                self._active_href = urljoin(self.base_url, href)
                self._active_text = []
        elif tag == "time":
            value = attrs_dict.get("datetime") or attrs_dict.get("title")
            if value:
                self.times.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "a" and self._active_href:
            text = clean_text(" ".join(self._active_text))
            if text:
                self.links.append((text, self._active_href))
            self._active_href = None
            self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._active_href:
            self._active_text.append(data)

    @property
    def page_title(self) -> str:
        return clean_text(" ".join(self.title_parts))


def clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_match(value: str) -> str:
    text = clean_text(value).lower()
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9+#.\- ]+", " ", text)


def iso_week_start_utc(dt: datetime) -> datetime:
    d = dt.astimezone(timezone.utc)
    monday = d - timedelta(days=d.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def build_windows(now: datetime) -> list[tuple[datetime, datetime]]:
    end_week = iso_week_start_utc(now)
    start = end_week - timedelta(weeks=WINDOW_WEEKS)
    return [(start + timedelta(weeks=i), start + timedelta(weeks=i + 1)) for i in range(WINDOW_WEEKS)]


def format_week_label(dt: datetime) -> str:
    return dt.strftime("%d.%m")


def host_of(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    host = (parsed.netloc or parsed.path).lower()
    return host[4:] if host.startswith("www.") else host


def authority_score(url_or_host: str | None) -> float:
    host = host_of(url_or_host)
    if not host:
        return 0.0
    best = 0.0
    for authority_host, score in AUTHORITY_DOMAINS.items():
        if host == authority_host or host.endswith("." + authority_host):
            best = max(best, score)
    return best


def authority_family(url_or_host: str | None) -> str:
    host = host_of(url_or_host)
    if not host:
        return "unknown"
    if host.endswith("owasp.org"):
        return "owasp"
    if host.endswith("cloudsecurityalliance.org"):
        return "csa"
    if host.endswith("openai.com"):
        return "openai"
    if host.endswith("anthropic.com"):
        return "anthropic"
    if host.endswith("google.com") or host.endswith("googleblog.com") or host.endswith("blog.google") or host.endswith("deepmind.google"):
        return "google"
    if host.endswith("microsoft.com"):
        return "microsoft"
    if host.endswith("aws.amazon.com") or host.endswith("amazon.com"):
        return "aws"
    return host


def source_priority(source: Source) -> tuple[int, str]:
    priority = 0 if authority_score(source.url) > 0 else 1
    return priority, source.url


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    clean = parsed._replace(fragment="")
    return clean.geturl().rstrip("/").lower()


def load_keywords() -> list[dict[str, str]]:
    config = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for category in config.get("categories", []):
        for item in category.get("keywords", []):
            query = clean_text(item.get("query"))
            if not query:
                continue
            key = query.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "label": clean_text(item.get("label") or query),
                "query": query,
                "category": clean_text(category.get("name") or "Uncategorized"),
            })
    return out


def load_sources() -> list[Source]:
    config = json.loads(SEARCH_SOURCES_PATH.read_text(encoding="utf-8"))
    sources: list[Source] = []
    seen: set[str] = set()
    for category in config.get("categories", []):
        access = str(category.get("access") or "")
        if access != "public":
            continue
        category_id = str(category.get("id") or "public")
        for url in category.get("sources", []):
            normalized = normalize_url(url)
            if normalized and normalized not in seen:
                seen.add(normalized)
                sources.append(Source(url=url, category=category_id))
    return sorted(sources, key=source_priority)


def fetch_text(url: str, timeout: int) -> tuple[str, str] | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("content-type", "")
            raw = resp.read(1_500_000)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None

    encoding = "utf-8"
    match = re.search(r"charset=([\w.-]+)", content_type, re.I)
    if match:
        encoding = match.group(1)
    try:
        return raw.decode(encoding, errors="replace"), content_type
    except LookupError:
        return raw.decode("utf-8", errors="replace"), content_type


def is_feed(content_type: str, text: str) -> bool:
    head = text[:300].lower()
    return "xml" in content_type.lower() or "<rss" in head or "<feed" in head or "<rdf" in head


def parse_date(value: object) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    iso_match = re.search(r"\d{4}-\d{2}-\d{2}(?:[tT ][0-9:.+-zZ]*)?", text)
    if iso_match:
        iso_text = iso_match.group(0).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso_text)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except ValueError:
            pass
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S %z",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text[:40], fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def xml_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(node):
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in names and child.text:
            return clean_text(child.text)
    return ""


def xml_link(node: ET.Element) -> str:
    for child in list(node):
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local == "link":
            href = child.attrib.get("href")
            if href:
                return href
            if child.text:
                return clean_text(child.text)
    return ""


def parse_feed(text: str, source: Source, feed_url: str) -> list[Item]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    out: list[Item] = []
    for node in root.iter():
        local = node.tag.rsplit("}", 1)[-1].lower()
        if local not in {"item", "entry"}:
            continue
        title = xml_text(node, ("title",))
        link = xml_link(node) or feed_url
        summary = xml_text(node, ("description", "summary", "content", "encoded"))
        date = parse_date(xml_text(node, ("pubdate", "published", "updated", "date", "dc:date")))
        if title or summary:
            out.append(Item(title=title or link, url=urljoin(feed_url, link), summary=summary, source_url=source.url, source_host=host_of(source.url), published=date))
    return out


def parse_html(text: str, source: Source, page_url: str) -> tuple[list[Item], set[str]]:
    parser = SourceHTMLParser(page_url)
    try:
        parser.feed(text)
    except Exception:
        pass
    host = host_of(page_url)
    items: list[Item] = []
    page_date = parse_date(" ".join(parser.times[:3]))
    if parser.page_title or parser.meta_description:
        items.append(Item(
            title=parser.page_title or host,
            url=page_url,
            summary=parser.meta_description,
            source_url=source.url,
            source_host=host,
            published=page_date,
        ))
    for title, link in parser.links[:120]:
        if not link.startswith(("http://", "https://")):
            continue
        if len(title) < 8:
            continue
        items.append(Item(title=title, url=link, summary="", source_url=source.url, source_host=host_of(link) or host, published=page_date))
    return items, parser.feed_links


def feed_candidates(url: str, discovered: set[str]) -> list[str]:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    candidates = list(discovered)
    if parsed.path and not parsed.path.endswith("/"):
        candidates.append(url.rstrip("/") + "/feed")
    for hint in RSS_HINTS:
        candidates.append(base.rstrip("/") + "/" + hint)
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalize_url(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(candidate)
    return out


def keyword_matches(item: Item, keywords: list[dict[str, str]], max_matches: int) -> list[dict[str, str]]:
    haystack = normalize_for_match(f"{item.title} {item.summary} {item.url}")
    matched: list[dict[str, str]] = []
    for keyword in keywords:
        query = normalize_for_match(keyword["query"])
        if not query:
            continue
        tokens = [token for token in query.split() if len(token) > 1]
        exact = query in haystack
        fuzzy = len(tokens) >= 2 and all(re.search(rf"\b{re.escape(token)}\b", haystack) for token in tokens)
        single = len(tokens) == 1 and re.search(rf"\b{re.escape(tokens[0])}\b", haystack)
        if exact or fuzzy or single:
            matched.append(keyword)
            if len(matched) >= max_matches:
                break
    return matched


def is_dashboard_specific_tag(item: dict[str, object]) -> bool:
    label = normalize_for_match(str(item.get("label") or ""))
    return label not in GENERIC_DASHBOARD_QUERIES


def dashboard_keyword_score(item: dict[str, object]) -> float:
    label = normalize_for_match(str(item.get("label") or ""))
    total = float(item.get("total") or 0)
    score = total
    if label in TREND_FOCUS_QUERIES:
        score += 12.0
    if any(token in label for token in ("mcp", "prompt", "guardrail", "agent", "tool", "rag", "jailbreak")):
        score += 4.0
    return score


def within_window(dt: datetime | None, windows: list[tuple[datetime, datetime]]) -> bool:
    if not dt:
        return False
    return windows[0][0] <= dt < windows[-1][1] + timedelta(days=7)


def bucket_index(dt: datetime | None, windows: list[tuple[datetime, datetime]], fallback: int) -> int | None:
    if dt:
        for index, (start, end) in enumerate(windows):
            if start <= dt < end:
                return index
        return None
    return fallback % len(windows)


def avg(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def growth_percent_points(series: list[int]) -> list[float]:
    chunk = max(1, len(series) // 3)
    start = avg(series[:chunk])
    mid = avg(series[chunk:chunk * 2])
    end = avg(series[chunk * 2:])
    baseline = max(1.0, start)
    return [0.0, round(((mid - start) / baseline) * 100, 2), round(((end - start) / baseline) * 100, 2)]


def doc_relevance_score(item: Item, matches: list[dict[str, str]]) -> float:
    title = normalize_for_match(item.title)
    unique_queries = {normalize_for_match(match["query"]) for match in matches}
    unique_queries.discard("")
    score = len(unique_queries) * 2.0
    for query in unique_queries:
        tokens = [token for token in query.split() if len(token) > 1]
        score += min(2.5, len(tokens) * 0.35)
        if query in title:
            score += 2.0
        elif tokens and all(re.search(rf"\b{re.escape(token)}\b", title) for token in tokens):
            score += 1.25
    return score


def add_doc_candidate(
    doc_scores: dict[str, dict[str, object]],
    item: Item,
    matches: list[dict[str, str]],
    windows: list[tuple[datetime, datetime]],
    curated: bool = False,
) -> None:
    doc_key = normalize_url(item.url) or item.title.lower()
    host = item.source_host or host_of(item.url) or "public web source"
    doc = doc_scores.setdefault(doc_key, {
        "title": item.title[:180],
        "publisher": host,
        "summary": clean_text(item.summary),
        "date": item.published.date().isoformat() if item.published else "",
        "url": item.url,
        "labels": [],
        "mentions": 0,
        "referrers": set(),
        "relevanceScore": 0.0,
        "authorityScore": authority_score(item.url),
        "recencyScore": recency_score(item.published, windows),
        "curated": curated,
        "family": authority_family(item.url),
    })
    doc["mentions"] = int(doc["mentions"]) + 1
    doc["referrers"].add(host_of(item.source_url) or host)
    doc["relevanceScore"] = max(float(doc["relevanceScore"]), doc_relevance_score(item, matches))
    doc["authorityScore"] = max(float(doc["authorityScore"]), authority_score(item.url), authority_score(host))
    doc["recencyScore"] = max(float(doc["recencyScore"]), recency_score(item.published, windows))
    doc["curated"] = bool(doc.get("curated")) or curated
    doc["family"] = authority_family(item.url)
    if clean_text(item.summary) and not doc.get("summary"):
        doc["summary"] = clean_text(item.summary)
    labels = doc["labels"]
    for match in matches:
        if match["label"] not in labels:
            labels.append(match["label"])


def recency_score(published: datetime | None, windows: list[tuple[datetime, datetime]]) -> float:
    if not published:
        return 0.0
    window_start, window_end = windows[0][0], windows[-1][1]
    if window_start <= published < window_end:
        days_old = max(0, (window_end - published).days)
        return max(0.5, 2.5 - days_old / 45)
    return 0.5


def document_format_score(doc: dict[str, object]) -> float:
    text = normalize_for_match(f"{doc.get('title', '')} {doc.get('summary', '')} {doc.get('url', '')}")
    score = 0.0
    if any(term in text for term in ("state of", "report", "whitepaper", "guide", "framework", "landscape", "discussion paper", "research note")):
        score += 4.0
    if any(term in text for term in ("governance", "risk", "mitigation", "security and governance", "threats and mitigations")):
        score += 2.0
    if ".pdf" in text:
        score += 1.5
    if any(term in text for term in ("ctf", "summit", "event", "webinar", "workshop", "join us")):
        score -= 4.0
    return score


def format_doc_reason(doc: dict[str, object]) -> str:
    parts = [
        f"keywords: {', '.join(str(label) for label in doc.get('labels', [])[:4])}",
        f"relevance {float(doc.get('relevanceScore', 0)):.1f}",
    ]
    authority = float(doc.get("authorityScore", 0))
    if authority:
        parts.append(f"authority {authority:.1f}")
    mentions = int(doc.get("mentions", 0))
    if mentions > 1:
        parts.append(f"{mentions} observed mentions")
    if doc.get("curated"):
        parts.append("verified curated source")
    format_score = float(doc.get("formatScore", 0))
    if format_score > 0:
        parts.append(f"format {format_score:.1f}")
    summary = clean_text(doc.get("summary") or "")
    if summary:
        parts.append(summary[:140])
    return "; ".join(parts)


def select_diverse_top_docs(ranked_docs: list[dict[str, object]], limit: int = 5) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    family_counts: dict[str, int] = {}
    host_counts: dict[str, int] = {}

    for doc in ranked_docs:
        family = str(doc.get("family") or authority_family(str(doc.get("url") or "")))
        host = host_of(str(doc.get("url") or "")) or str(doc.get("publisher") or "")
        if family_counts.get(family, 0) >= 2:
            continue
        if host_counts.get(host, 0) >= 2:
            continue
        selected.append(doc)
        family_counts[family] = family_counts.get(family, 0) + 1
        host_counts[host] = host_counts.get(host, 0) + 1
        if len(selected) == limit:
            return selected

    for doc in ranked_docs:
        if doc not in selected:
            selected.append(doc)
        if len(selected) == limit:
            break
    return selected


def collect_items(sources: list[Source], timeout: int, delay_seconds: float, max_sources: int) -> list[Item]:
    items: list[Item] = []
    for index, source in enumerate(sources[:max_sources], start=1):
        fetched = fetch_text(source.url, timeout)
        if not fetched:
            print(f"  [{index:03d}/{min(len(sources), max_sources):03d}] skip {source.url}")
            continue
        text, content_type = fetched
        source_items: list[Item] = []
        discovered_feeds: set[str] = set()
        if is_feed(content_type, text):
            source_items.extend(parse_feed(text, source, source.url))
        else:
            html_items, discovered_feeds = parse_html(text, source, source.url)
            source_items.extend(html_items)
            for feed_url in feed_candidates(source.url, discovered_feeds)[:4]:
                feed = fetch_text(feed_url, timeout)
                if not feed:
                    continue
                feed_text, feed_type = feed
                if is_feed(feed_type, feed_text):
                    source_items.extend(parse_feed(feed_text, source, feed_url))
                    if len(source_items) > len(html_items):
                        break
        items.extend(source_items)
        print(f"  [{index:03d}/{min(len(sources), max_sources):03d}] {len(source_items):4d} items {source.url}")
        time.sleep(delay_seconds)
    return items


def build_output(items: list[Item], keywords: list[dict[str, str]], windows: list[tuple[datetime, datetime]]) -> dict:
    series_by_label = {kw["label"]: [0 for _ in windows] for kw in keywords}
    totals_by_label = {kw["label"]: {"label": kw["label"], "category": kw["category"], "total": 0} for kw in keywords}
    source_counts: dict[str, int] = {}
    doc_scores: dict[str, dict[str, object]] = {}

    for index, item in enumerate(items):
        if item.published and not within_window(item.published, windows):
            continue
        matches = keyword_matches(item, keywords, max_matches=6)
        if not matches:
            continue
        bucket = bucket_index(item.published, windows, index)
        if bucket is None:
            continue
        source_counts[item.source_host or host_of(item.url)] = source_counts.get(item.source_host or host_of(item.url), 0) + 1
        if item.published and within_window(item.published, windows):
            add_doc_candidate(doc_scores, item, matches, windows)
        for match in matches:
            label = match["label"]
            series_by_label[label][bucket] += 1
            totals_by_label[label]["total"] += 1

    totals = sorted((item for item in totals_by_label.values() if item["total"] > 0), key=lambda item: item["total"], reverse=True)
    dashboard_totals = sorted(
        (item for item in totals if is_dashboard_specific_tag(item)),
        key=lambda item: (dashboard_keyword_score(item), item["total"]),
        reverse=True,
    )
    top5 = dashboard_totals[:5]
    chart_keywords = [{"key": item["label"], "color": PALETTE[index % len(PALETTE)]} for index, item in enumerate(top5)]
    chart_series = {item["label"]: series_by_label[item["label"]] for item in top5}

    growth_candidates = []
    for item in dashboard_totals:
        points = growth_percent_points(series_by_label[item["label"]])
        growth_candidates.append({**item, "growthPoints": points, "growthPercent": points[-1]})
    growth_top5 = sorted(growth_candidates, key=lambda item: (item["growthPercent"], item["total"]), reverse=True)[:5]
    growth_keywords = [{"key": item["label"], "color": PALETTE[index % len(PALETTE)]} for index, item in enumerate(growth_top5)]
    growth_series = {item["label"]: item["growthPoints"] for item in growth_top5}

    top_sources = [
        {"name": host, "count": count, "url": f"https://{host}", "category": "scraped_public_source", "access": "public"}
        for host, count in sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]

    now = datetime.now(timezone.utc)
    key_documents = json.loads(KEY_DOCUMENTS_PATH.read_text(encoding="utf-8"))
    for document in key_documents.get("documents", []):
        published = parse_date(document.get("date"))
        if not within_window(published, windows):
            continue
        curated_item = Item(
            title=clean_text(document.get("title")),
            url=clean_text(document.get("url")),
            summary=clean_text(document.get("why")),
            source_url=clean_text(document.get("url")),
            source_host=host_of(clean_text(document.get("url"))) or clean_text(document.get("publisher")),
            published=published,
        )
        matches = keyword_matches(curated_item, keywords, max_matches=6)
        if matches:
            add_doc_candidate(doc_scores, curated_item, matches, windows, curated=True)
    ranked_docs = []
    for doc in doc_scores.values():
        if not doc.get("date"):
            continue
        format_score = document_format_score(doc)
        if format_score <= 0:
            continue
        mentions = int(doc["mentions"])
        referrer_count = len(doc["referrers"])
        citation_score = min(4.0, max(0, mentions - 1) * 0.7 + max(0, referrer_count - 1) * 0.8)
        total_score = (
            float(doc["relevanceScore"])
            + float(doc["authorityScore"])
            + float(doc["recencyScore"])
            + format_score
            + citation_score
        )
        doc["score"] = round(total_score, 2)
        doc["citationScore"] = round(citation_score, 2)
        doc["formatScore"] = round(format_score, 2)
        doc["why"] = format_doc_reason(doc)
        doc["referrers"] = sorted(doc["referrers"])
        ranked_docs.append(doc)
    sorted_docs = sorted(
        ranked_docs,
        key=lambda doc: (
            float(doc["score"]),
            float(doc["relevanceScore"]),
            float(doc["authorityScore"]),
            int(doc["mentions"]),
        ),
        reverse=True,
    )
    top_docs = [
        {
            "title": str(doc["title"]),
            "publisher": str(doc["publisher"]),
            "why": str(doc["why"]),
            "date": str(doc["date"]),
            "url": str(doc["url"]),
        }
        for doc in select_diverse_top_docs(sorted_docs, limit=5)
    ] or key_documents.get("documents", [])[:5]
    return {
        "meta": {
            "generatedAt": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "windowWeeks": WINDOW_WEEKS,
            "mentionsMetric": "rss_html_keyword_matches",
            "source": "Public RSS/HTML scraping",
            "note": f"Parsed {len(items)} public RSS/HTML items and matched {sum(item['total'] for item in totals)} keyword mentions.",
        },
        "weekLabels": [format_week_label(start) for start, _ in windows],
        "keywords": chart_keywords,
        "seriesByKeyword": chart_series,
        "growthLabels": ["Начало", "Середина", "Конец"],
        "growthKeywords": growth_keywords,
        "growthSeriesByKeyword": growth_series,
        "keywordTotals": totals,
        "topDocs": top_docs,
        "topSources": top_sources,
        "observedSources": top_sources,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    sources = load_sources()
    keywords = load_keywords()
    windows = build_windows(datetime.now(timezone.utc))

    print(f"Sources: {len(sources)} public; scanning: {min(len(sources), args.max_sources)}")
    print(f"Keywords: {len(keywords)}")
    items = collect_items(sources, args.timeout, args.delay_seconds, args.max_sources)
    output = build_output(items, keywords, windows)

    if not output["keywords"]:
        print("ERROR: no keyword matches found; increase --max-sources or check network access.", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Top keywords: {', '.join(item['key'] for item in output['keywords'])}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect AI Security trend data from public RSS and HTML sources.")
    parser.add_argument("--max-sources", type=int, default=120, help="Maximum public source URLs to scan.")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout per request in seconds.")
    parser.add_argument("--delay-seconds", type=float, default=0.25, help="Delay between source requests.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Path to write dashboard data JSON.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
