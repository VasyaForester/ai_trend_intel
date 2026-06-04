"""Collect AI Security trend data from SerpAPI DuckDuckGo search.

It reads the keyword taxonomy, queries SerpAPI, and writes `ui/data.json` for
the dashboard.

Required environment:
    SERPAPI_API_KEY=<your key>

Run:
    python scripts/collect_serpapi.py --engine duckduckgo

Notes:
- The API key is intentionally read from the environment and must not be
  committed to the repository.
- DuckDuckGo does not reliably expose total result counts, so keyword volume and
  source rankings are based on the organic results returned by SerpAPI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
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


def avg(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def growth_percent_points(series: list[int]) -> list[float] | None:
    """Return [start%, mid%, end%] by thirds of the observed time series."""
    if len(series) < 3:
        return None
    chunk = max(1, len(series) // 3)
    start_value = avg(series[:chunk])
    mid_value = avg(series[chunk:chunk * 2])
    end_value = avg(series[chunk * 2:])
    baseline = max(1.0, start_value)
    mid_growth = ((mid_value - start_value) / baseline) * 100
    end_growth = ((end_value - start_value) / baseline) * 100
    return [0.0, round(mid_growth, 2), round(end_growth, 2)]


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


def search_queries(query: str) -> list[str]:
    return [
        f'"{query}" AI security',
        f'"{query}" LLM security',
        f'"{query}" AI agent security',
        f'"{query}" cybersecurity',
        f'{query} AI security',
    ]


def date_filter(start: datetime, end: datetime, engine: str) -> str | None:
    if engine == "duckduckgo":
        return f"{start:%Y-%m-%d}..{end:%Y-%m-%d}"
    return None


def serpapi_search(
    api_key: str,
    engine: str,
    query: str,
    num_results: int,
    date_filter: str | None = None,
    retries: int = 4,
) -> dict:
    params = {
        "engine": engine,
        "q": query,
        "api_key": api_key,
    }
    if engine == "duckduckgo":
        params["kl"] = "wt-wt"
        params["m"] = str(num_results)
        if date_filter:
            params["df"] = date_filter
    else:
        params["num"] = str(num_results)
    url = SERPAPI_URL + "?" + urllib.parse.urlencode(params)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ai-trend-intel/1.0 (research)"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError(
                    "SerpAPI rejected SERPAPI_API_KEY. Re-run scripts/setup_serpapi_key.ps1 with a valid key."
                ) from exc
            last_error = exc
            if attempt < retries - 1:
                time.sleep(min(60, 5 * (attempt + 1)))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(min(60, 5 * (attempt + 1)))
    raise RuntimeError(f"SerpAPI query failed after {retries} attempts: {last_error}")


def result_count(data: dict) -> int:
    info = data.get("search_information") or {}
    for key in ("total_results",):
        value = info.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.replace(",", "").isdigit():
            return int(value.replace(",", ""))
    return len(data.get("organic_results") or [])


def organic_results(data: dict) -> list[dict]:
    return data.get("organic_results") or data.get("results") or []


def normalize_link(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.scheme and not parsed.netloc:
        return url.strip().lower() or None
    clean = parsed._replace(fragment="", query="")
    return clean.geturl().rstrip("/").lower()


def parse_result_date(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso_match:
        try:
            return datetime.fromisoformat(iso_match.group(0)).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match:
        try:
            return datetime(int(year_match.group(1)), 1, 1, tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def result_date(item: dict) -> datetime | None:
    return parse_result_date(item.get("date_raw")) or parse_result_date(item.get("date"))


def bucket_index_for_date(dt: datetime, windows: list[tuple[datetime, datetime]]) -> int | None:
    for idx, (start, end) in enumerate(windows):
        if start <= dt < end:
            return idx
    return None


def fallback_bucket(index: int, total: int, windows_count: int) -> int:
    if windows_count <= 1:
        return 0
    if total <= 1:
        return windows_count - 1
    # Undated DuckDuckGo results are relevance-ranked, not time-ranked. Spread them
    # across the period so sparse date metadata does not collapse every trend to zero.
    return min(windows_count - 1, int(index * windows_count / total))


def collect_keyword_results(
    api_key: str,
    engine: str,
    query: str,
    num_results: int,
    window_start: datetime,
    window_end: datetime,
    delay_seconds: float,
) -> list[dict]:
    seen: set[str] = set()
    collected: list[dict] = []
    full_window_filter = date_filter(window_start, window_end, engine)

    for search_query in search_queries(query):
        variants = [full_window_filter, None] if engine == "duckduckgo" else [None]
        for current_filter in variants:
            data = serpapi_search(api_key, engine, search_query, num_results, current_filter)
            results = organic_results(data)
            for item in results:
                key = normalize_link(item.get("link") or item.get("url"))
                if not key or key in seen:
                    continue
                seen.add(key)
                collected.append(item)
            if results:
                break
        time.sleep(delay_seconds)

    return collected


def weekly_series_from_results(results: list[dict], windows: list[tuple[datetime, datetime]]) -> list[int]:
    series = [0 for _ in windows]
    undated: list[dict] = []
    for item in results:
        dt = result_date(item)
        idx = bucket_index_for_date(dt, windows) if dt else None
        if idx is None:
            undated.append(item)
        else:
            series[idx] += 1

    for index, _item in enumerate(undated):
        series[fallback_bucket(index, len(undated), len(windows))] += 1
    return series


def source_metadata(host: str, registry: dict[str, dict[str, object]], count: int) -> dict[str, object]:
    source = registry.get(host)
    if source:
        return {**source, "count": count}
    return {
        "name": host,
        "url": f"https://{host}",
        "category": "duckduckgo_organic_result",
        "access": "public",
        "count": count,
    }


def collect_source_hits(
    results: list[dict],
    registry: dict[str, dict[str, object]],
    counts: dict[str, int],
    seen_links: set[str],
) -> None:
    for item in results:
        link = item.get("link") or item.get("url")
        host = host_of(link)
        if not host:
            continue
        dedupe_key = normalize_link(link) or host
        if dedupe_key in seen_links:
            continue
        seen_links.add(dedupe_key)
        matched_host = None
        if host in registry:
            matched_host = host
        else:
            for configured_host in registry:
                if host.endswith("." + configured_host):
                    matched_host = configured_host
                    break
        counts[matched_host or host] = counts.get(matched_host or host, 0) + 1


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
    seen_source_links: set[str] = set()

    print(f"Window: {window_start.date()} .. {window_end.date()} ({WINDOW_WEEKS} completed weeks)")
    print(f"Keywords: {len(keywords)}; engine: {args.engine}; registry hosts: {len(registry)}")

    totals = []
    all_series_by_keyword: dict[str, list[int]] = {}
    for index, kw in enumerate(keywords, start=1):
        try:
            results = collect_keyword_results(
                api_key,
                args.engine,
                kw["query"],
                args.num_results,
                window_start,
                window_end,
                args.delay_seconds,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        weekly = weekly_series_from_results(results, windows)
        collect_source_hits(results, registry, source_counts, seen_source_links)
        all_series_by_keyword[kw["label"]] = weekly
        total = sum(weekly)
        totals.append({"label": kw["label"], "query": kw["query"], "category": kw["category"], "total": total})
        print(f"  [{index:02d}/{len(keywords):02d}] {total:8d} {kw['label']} weekly={weekly}")

    totals.sort(key=lambda item: item["total"], reverse=True)
    top5 = totals[:5]

    series_by_keyword = {kw["label"]: all_series_by_keyword[kw["label"]] for kw in top5}
    chart_keywords = [
        {"key": kw["label"], "color": PALETTE[idx % len(PALETTE)]}
        for idx, kw in enumerate(top5)
    ]

    growth_candidates = []
    for kw in totals:
        points = growth_percent_points(all_series_by_keyword.get(kw["label"], []))
        if points:
            growth_candidates.append({**kw, "growthPoints": points, "growthPercent": points[-1]})
    growth_top5 = sorted(
        growth_candidates,
        key=lambda x: (x["growthPercent"], x["total"]),
        reverse=True,
    )[:5]
    growth_series_by_keyword = {kw["label"]: kw["growthPoints"] for kw in growth_top5}
    growth_keywords = [
        {"key": kw["label"], "color": PALETTE[idx % len(PALETTE)]}
        for idx, kw in enumerate(growth_top5)
    ]

    observed_sources = [
        source_metadata(host, count, registry)
        for host, count in sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]
    top_sources = observed_sources[:5]

    out = {
        "meta": {
            "generatedAt": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "windowWeeks": WINDOW_WEEKS,
            "mentionsMetric": "serpapi_duckduckgo_organic_results",
            "source": f"SerpAPI ({args.engine})",
            "note": "Counts and sources are parsed from SerpAPI DuckDuckGo organic results; undated results are distributed across the completed window.",
        },
        "weekLabels": [format_week_label(ws) for ws, _ in windows],
        "keywords": chart_keywords,
        "seriesByKeyword": series_by_keyword,
        "growthLabels": ["Начало", "Середина", "Конец"],
        "growthKeywords": growth_keywords,
        "growthSeriesByKeyword": growth_series_by_keyword,
        "keywordTotals": [
            {"label": item["label"], "category": item["category"], "total": item["total"]} for item in totals
        ],
        "topDocs": key_documents.get("documents", [])[:5],
        "topSources": top_sources,
        "observedSources": observed_sources[:25],
    }
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect AI Security trend data from SerpAPI.")
    parser.add_argument("--engine", default="duckduckgo", choices=["duckduckgo", "google"], help="SerpAPI engine.")
    parser.add_argument("--num-results", type=int, default=35, help="Organic results to inspect per query.")
    parser.add_argument("--delay-seconds", type=float, default=1.0, help="Delay between SerpAPI calls.")
    parser.add_argument("--keyword-limit", type=int, default=None, help="Limit keywords for smoke tests.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Path to write dashboard data JSON.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
