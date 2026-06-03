"""Collect REAL AI-security trend data from the Hacker News (Algolia) Search API.

Why Hacker News: its Algolia Search API is public, key-free, and returns an exact
`nbHits` count for any query within an arbitrary time window. That lets us compute
honest, reproducible per-week message counts (non-cumulative) instead of fabricated
numbers.

Output: writes ui/data.json consumed by the dashboard.

Run:
    python scripts/collect_hn.py

Notes:
- The mention chart shows the top-5 keywords (by total volume in the window).
- Weekly buckets are aligned to ISO weeks (Monday 00:00 UTC), matching the UI labels.
- Top documents = curated Q2 2026 documents from config/key_documents.json.
- Top sources = most frequent story domains among matched stories.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "keywords.json"
KEY_DOCUMENTS_PATH = ROOT / "config" / "key_documents.json"
SEARCH_SOURCES_PATH = ROOT / "config" / "search_sources.json"
OUTPUT_PATH = ROOT / "ui" / "data.json"

API = "https://hn.algolia.com/api/v1/search"
USER_AGENT = "ai-trend-intel/1.0 (research)"
WINDOW_WEEKS = 12
PALETTE = ["#22d3ee", "#a855f7", "#60a5fa", "#f59e0b", "#34d399", "#f472b6", "#facc15"]


def iso_week_start_utc(dt: datetime) -> datetime:
    """Monday 00:00 UTC of the week containing dt."""
    d = dt.astimezone(timezone.utc)
    monday = d - timedelta(days=d.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def build_windows(now: datetime) -> list[tuple[datetime, datetime]]:
    # Use only fully completed weeks. If now is Wednesday, the week that
    # started on Monday is still incomplete and would undercount the last point.
    end_week = iso_week_start_utc(now)
    start = end_week - timedelta(weeks=WINDOW_WEEKS)
    windows = []
    for i in range(WINDOW_WEEKS):
        ws = start + timedelta(weeks=i)
        we = ws + timedelta(weeks=1)
        windows.append((ws, we))
    return windows


def hn_search(query: str, start_ts: int | None, end_ts: int | None, hits_per_page: int) -> dict:
    # Exact-phrase matching keeps counts real but on-topic (avoids generic partial matches).
    phrase = f'"{query}"'
    params = {
        "query": phrase,
        "tags": "story",
        "hitsPerPage": str(hits_per_page),
        "advancedSyntax": "true",
        "restrictSearchableAttributes": "title,story_text",
    }
    filters = []
    if start_ts is not None:
        filters.append(f"created_at_i>={start_ts}")
    if end_ts is not None:
        filters.append(f"created_at_i<{end_ts}")
    if filters:
        params["numericFilters"] = ",".join(filters)
    url = API + "?" + urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"HN query failed for {query!r}: {last_err}")


def host_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:  # noqa: BLE001
        return None


def format_week_label(dt: datetime) -> str:
    return dt.strftime("%d.%m")


def avg(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def growth_score(series: list[int]) -> float:
    if len(series) < 2:
        return 0.0
    midpoint = max(1, len(series) // 2)
    early = avg(series[:midpoint])
    late = avg(series[midpoint:])
    absolute_growth = late - early
    if absolute_growth <= 0:
        return 0.0
    # Low-base acceleration should rank above tiny relative movement on huge baselines.
    import math
    return math.log1p(absolute_growth) * math.log1p(late / max(1.0, early))


def host_of_source(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or parsed.path).lower()
    return host[4:] if host.startswith("www.") else host


def load_configured_source_map() -> dict[str, dict[str, object]]:
    if not SEARCH_SOURCES_PATH.exists():
        return {}
    registry = json.loads(SEARCH_SOURCES_PATH.read_text(encoding="utf-8"))
    sources: dict[str, dict[str, object]] = {}
    for category in registry.get("categories", []):
        if category.get("access") == "restricted":
            continue
        for url in category.get("sources", []):
            host = host_of_source(url)
            if host in sources:
                continue
            sources[host] = {
                "name": host,
                "count": 0,
                "url": url,
                "category": category.get("id", "unknown"),
                "access": category.get("access", "public"),
            }
    return sources


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    key_documents = json.loads(KEY_DOCUMENTS_PATH.read_text(encoding="utf-8"))
    keywords = []
    for cat in config.get("categories", []):
        for kw in cat.get("keywords", []):
            keywords.append({"label": kw["label"], "query": kw["query"], "category": cat["name"]})

    now = datetime.now(timezone.utc)
    windows = build_windows(now)
    window_start_ts = int(windows[0][0].timestamp())
    window_end_ts = int(windows[-1][1].timestamp())

    print(f"Window: {windows[0][0].date()} .. {windows[-1][1].date()} ({WINDOW_WEEKS} weeks)")
    print(f"Keywords: {len(keywords)}")

    totals = []
    collected_hits: dict[str, dict] = {}

    # Pass 1: total volume per keyword (full window) + sample hits for docs/sources.
    for kw in keywords:
        data = hn_search(kw["query"], window_start_ts, window_end_ts, hits_per_page=50)
        nb = int(data.get("nbHits", 0))
        totals.append({"label": kw["label"], "query": kw["query"], "category": kw["category"], "total": nb})
        for h in data.get("hits", []):
            oid = h.get("objectID")
            if oid and oid not in collected_hits:
                collected_hits[oid] = h
        print(f"  [{nb:5d}] {kw['label']}")
        time.sleep(0.15)

    totals.sort(key=lambda x: x["total"], reverse=True)
    top5 = totals[:5]

    # Pass 2: weekly counts (non-cumulative) for all keywords so volume and
    # growth dashboards can be ranked independently.
    all_series_by_keyword: dict[str, list[int]] = {}
    for kw in totals:
        weekly = []
        for (ws, we) in windows:
            data = hn_search(kw["query"], int(ws.timestamp()), int(we.timestamp()), hits_per_page=0)
            weekly.append(int(data.get("nbHits", 0)))
            time.sleep(0.15)
        all_series_by_keyword[kw["label"]] = weekly
        print(f"  weekly {kw['label']}: {weekly}")

    series_by_keyword = {kw["label"]: all_series_by_keyword[kw["label"]] for kw in top5}
    chart_keywords = [
        {"key": kw["label"], "color": PALETTE[idx % len(PALETTE)]}
        for idx, kw in enumerate(top5)
    ]

    growth_top5 = sorted(
        (
            {**kw, "growthScore": growth_score(all_series_by_keyword.get(kw["label"], []))}
            for kw in totals
        ),
        key=lambda x: (x["growthScore"], x["total"]),
        reverse=True,
    )[:5]
    growth_series_by_keyword = {kw["label"]: all_series_by_keyword[kw["label"]] for kw in growth_top5}
    growth_keywords = [
        {"key": kw["label"], "color": PALETTE[idx % len(PALETTE)]}
        for idx, kw in enumerate(growth_top5)
    ]

    # Top documents are curated and link-checked separately; do not derive them
    # from HN popularity because that can surface irrelevant posts.
    top_docs = key_documents.get("documents", [])[:5]

    # Observed sources: most frequent story domains among matched HN stories.
    configured_sources = load_configured_source_map()
    source_counts: dict[str, int] = {}
    for h in collected_hits.values():
        host = host_of(h.get("url"))
        if host:
            source_counts[host] = source_counts.get(host, 0) + 1
    observed_sources = sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    observed_sources_out = [
        {"name": name, "count": cnt, "url": f"https://{name}"} for name, cnt in observed_sources
    ]
    top_sources = [
        {**configured_sources[name], "count": cnt}
        for name, cnt in sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)
        if name in configured_sources
    ]
    top_sources_out = top_sources[:5]

    out = {
        "meta": {
            "generatedAt": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "windowWeeks": WINDOW_WEEKS,
            "mentionsMetric": "weekly_count",
            "source": "Hacker News (Algolia Search API)",
            "note": "Real, reproducible weekly mention counts from Hacker News stories. Curated Q2 2026 documents are loaded from config/key_documents.json.",
        },
        "weekLabels": [format_week_label(ws) for ws, _ in windows],
        "keywords": chart_keywords,
        "seriesByKeyword": series_by_keyword,
        "growthKeywords": growth_keywords,
        "growthSeriesByKeyword": growth_series_by_keyword,
        "keywordTotals": [
            {"label": t["label"], "category": t["category"], "total": t["total"]} for t in totals
        ],
        "topDocs": top_docs,
        "topSources": top_sources_out,
        "observedSources": observed_sources_out,
    }

    OUTPUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
