"""Collect AI Security trend data from SerpAPI web search.

This collector replaces the Hacker News-only pipeline with broader web search.
It reads the keyword taxonomy and source registry, queries SerpAPI, and writes
`ui/data.json` for the dashboard.

Required environment:
    SERPAPI_API_KEY=<your key>

Run:
    python scripts/collect_serpapi.py

Notes:
- The API key is intentionally read from the environment and must not be
  committed to the repository.
- Google is the default SerpAPI engine because it supports date operators
  (`after:` / `before:`) and exposes `search_information.total_results`.
- DuckDuckGo can be tested with `--engine duckduckgo`, but result counts may be
  less consistent depending on SerpAPI response fields.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS_PATH = ROOT / "config" / "keywords.json"
KEY_DOCUMENTS_PATH = ROOT / "config" / "key_documents.json"
SEARCH_SOURCES_PATH = ROOT / "config" / "search_sources.json"
OUTPUT_PATH = ROOT / "ui" / "data.json"
DOTENV_PATH = ROOT / ".env"

SERPAPI_URL = "https://serpapi.com/search.json"
WINDOW_WEEKS = 12
PALETTE = ["#22d3ee", "#a855f7", "#60a5fa", "#f59e0b", "#34d399", "#f472b6", "#facc15"]


def load_dotenv(path: Path = DOTENV_PATH) -> None:
    """Load KEY=VALUE pairs from .env without overriding existing env vars."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def iso_week_start_utc(dt: datetime) -> datetime:
    d = dt.astimezone(timezone.utc)
    monday = d - timedelta(days=d.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def build_windows(now: datetime) -> list[tuple[datetime, datetime]]:
    # Use completed weeks only; the current week would undercount.
    end_week = iso_week_start_utc(now)
    start = end_week - timedelta(weeks=WINDOW_WEEKS)
    return [(start + timedelta(weeks=i), start + timedelta(weeks=i + 1)) for i in range(WINDOW_WEEKS)]


def format_week_label(dt: datetime) -> str:
    return dt.strftime("%d.%m")


def host_of(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = (parsed.netloc or parsed.path).lower()
    return host[4:] if host.startswith("www.") else host


def load_keywords(limit: int | None = None) -> list[dict[str, str]]:
    config = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    out = []
    for category in config.get("categories", []):
        for item in category.get("keywords", []):
            out.append({"label": item["label"], "query": item["query"], "category": category["name"]})
    return out[:limit] if limit else out


def load_source_registry() -> dict[str, dict[str, object]]:
    registry = json.loads(SEARCH_SOURCES_PATH.read_text(encoding="utf-8"))
    sources: dict[str, dict[str, object]] = {}
    for category in registry.get("categories", []):
        if category.get("access") == "restricted":
            continue
        for url in category.get("sources", []):
            host = host_of(url)
            if not host or host in sources:
                continue
            sources[host] = {
                "name": host,
                "url": url,
                "category": category.get("id", "unknown"),
                "access": category.get("access", "public"),
            }
    return sources


def date_query(query: str, start: datetime, end: datetime) -> str:
    start_date = start.strftime("%Y-%m-%d")
    end_date = end.strftime("%Y-%m-%d")
    context = '("AI security" OR "LLM security" OR "AI agent security" OR "agentic AI security")'
    return f'"{query}" {context} after:{start_date} before:{end_date}'


def full_window_query(query: str, start: datetime, end: datetime) -> str:
    return date_query(query, start, end)


def serpapi_search(api_key: str, engine: str, query: str, num_results: int, retries: int = 4) -> dict:
    params = {
        "engine": engine,
        "q": query,
        "api_key": api_key,
        "num": str(num_results),
    }
    url = SERPAPI_URL + "?" + urllib.parse.urlencode(params)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ai-trend-intel/1.0 (research)"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.load(resp)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(min(60, 5 * (attempt + 1)))
    raise RuntimeError(f"SerpAPI query failed after {retries} attempts: {last_error}")


def result_count(data: dict) -> int:
    info = data.get("search_information") or {}
    for key in ("total_results", "organic_results_state"):
        value = info.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.replace(",", "").isdigit():
            return int(value.replace(",", ""))
    return len(data.get("organic_results") or [])


def organic_results(data: dict) -> list[dict]:
    return data.get("organic_results") or data.get("results") or []


def collect_source_hits(results: list[dict], registry: dict[str, dict[str, object]], counts: dict[str, int]) -> None:
    for item in results:
        host = host_of(item.get("link") or item.get("url"))
        if not host:
            continue
        matched_host = None
        if host in registry:
            matched_host = host
        else:
            for configured_host in registry:
                if host.endswith("." + configured_host):
                    matched_host = configured_host
                    break
        if matched_host:
            counts[matched_host] = counts.get(matched_host, 0) + 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    load_dotenv()
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        print("ERROR: SERPAPI_API_KEY is not set. Add it to local .env or set it in PowerShell.", file=sys.stderr)
        return 2

    keywords = load_keywords(args.keyword_limit)
    key_documents = json.loads(KEY_DOCUMENTS_PATH.read_text(encoding="utf-8"))
    registry = load_source_registry()
    now = datetime.now(timezone.utc)
    windows = build_windows(now)
    window_start, window_end = windows[0][0], windows[-1][1]
    source_counts: dict[str, int] = {}

    print(f"Window: {window_start.date()} .. {window_end.date()} ({WINDOW_WEEKS} completed weeks)")
    print(f"Keywords: {len(keywords)}; engine: {args.engine}; registry hosts: {len(registry)}")

    totals = []
    for index, kw in enumerate(keywords, start=1):
        q = full_window_query(kw["query"], window_start, window_end)
        data = serpapi_search(api_key, args.engine, q, args.num_results)
        total = result_count(data)
        collect_source_hits(organic_results(data), registry, source_counts)
        totals.append({"label": kw["label"], "query": kw["query"], "category": kw["category"], "total": total})
        print(f"  [{index:02d}/{len(keywords):02d}] {total:8d} {kw['label']}")
        time.sleep(args.delay_seconds)

    totals.sort(key=lambda item: item["total"], reverse=True)
    top5 = totals[:5]

    series_by_keyword: dict[str, list[int]] = {}
    chart_keywords = []
    for idx, kw in enumerate(top5):
        weekly = []
        for ws, we in windows:
            q = date_query(kw["query"], ws, we)
            data = serpapi_search(api_key, args.engine, q, args.num_results)
            weekly.append(result_count(data))
            collect_source_hits(organic_results(data), registry, source_counts)
            time.sleep(args.delay_seconds)
        series_by_keyword[kw["label"]] = weekly
        chart_keywords.append({"key": kw["label"], "color": PALETTE[idx % len(PALETTE)]})
        print(f"  weekly {kw['label']}: {weekly}")

    top_sources = []
    for host, count in sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]:
        source = registry[host]
        top_sources.append({**source, "count": count})

    out = {
        "meta": {
            "generatedAt": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "windowWeeks": WINDOW_WEEKS,
            "mentionsMetric": "serpapi_weekly_result_count",
            "source": f"SerpAPI ({args.engine})",
            "note": "Counts are produced from SerpAPI web search over completed weekly windows and matched against config/search_sources.json.",
        },
        "weekLabels": [format_week_label(ws) for ws, _ in windows],
        "keywords": chart_keywords,
        "seriesByKeyword": series_by_keyword,
        "keywordTotals": [
            {"label": item["label"], "category": item["category"], "total": item["total"]} for item in totals
        ],
        "topDocs": key_documents.get("documents", [])[:5],
        "topSources": top_sources,
    }
    OUTPUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect AI Security trend data from SerpAPI.")
    parser.add_argument("--engine", default="google", choices=["google", "duckduckgo"], help="SerpAPI engine.")
    parser.add_argument("--num-results", type=int, default=10, help="Organic results to inspect per query.")
    parser.add_argument("--delay-seconds", type=float, default=1.0, help="Delay between SerpAPI calls.")
    parser.add_argument("--keyword-limit", type=int, default=None, help="Limit keywords for smoke tests.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
