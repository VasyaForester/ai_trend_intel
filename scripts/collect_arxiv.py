"""Collect and persist arXiv links for the AI security taxonomy.

The arXiv API is public and does not require an API key. It does require polite
usage: one connection at a time and at most one request every three seconds.

Run once:
    python scripts/collect_arxiv.py

Run forever every 10 minutes:
    python scripts/collect_arxiv.py --watch --interval-minutes 10

Outputs:
    data/arxiv_links.json      local accumulated cache (ignored by git)
    ui/arxiv_links.json        copy consumed by the static dashboard
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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS_PATH = ROOT / "config" / "keywords.json"
LOCAL_OUTPUT_PATH = ROOT / "data" / "arxiv_links.json"
UI_OUTPUT_PATH = ROOT / "ui" / "arxiv_links.json"

API_URL = "https://export.arxiv.org/api/query"
DEFAULT_USER_AGENT = "ai-trend-intel/1.0 (research; contact: configure-ARXIV_USER_AGENT)"
DEFAULT_CATEGORIES = ("cs.CR", "cs.AI", "cs.CL", "cs.LG")
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_keywords(limit: int | None = None) -> list[dict[str, str]]:
    config = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    out: list[dict[str, str]] = []
    for category in config.get("categories", []):
        for item in category.get("keywords", []):
            out.append({
                "label": item["label"],
                "query": item["query"],
                "category": category["name"],
            })
    return out[:limit] if limit else out


def load_cache() -> dict[str, Any]:
    if LOCAL_OUTPUT_PATH.exists():
        return json.loads(LOCAL_OUTPUT_PATH.read_text(encoding="utf-8"))
    if UI_OUTPUT_PATH.exists():
        return json.loads(UI_OUTPUT_PATH.read_text(encoding="utf-8"))
    return {
        "meta": {
            "source": "arXiv API",
            "generatedAt": None,
            "totalPapers": 0,
            "note": "Accumulated arXiv links collected by scripts/collect_arxiv.py.",
        },
        "papers": [],
    }


def save_cache(cache: dict[str, Any]) -> None:
    cache["meta"]["generatedAt"] = utc_now()
    cache["meta"]["totalPapers"] = len(cache.get("papers", []))
    LOCAL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    UI_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(cache, ensure_ascii=False, indent=2) + "\n"
    LOCAL_OUTPUT_PATH.write_text(payload, encoding="utf-8")
    UI_OUTPUT_PATH.write_text(payload, encoding="utf-8")


def build_query(phrase: str, categories: tuple[str, ...]) -> str:
    quoted_phrase = f'all:"{phrase}"'
    category_part = " OR ".join(f"cat:{cat}" for cat in categories)
    return f"{quoted_phrase} AND ({category_part})"


def fetch_arxiv(query: str, max_results: int, user_agent: str, attempts: int = 4) -> bytes:
    params = {
        "search_query": query,
        "start": "0",
        "max_results": str(max_results),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(req, timeout=45) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            # arXiv can temporarily return 429; back off more than the base 3s rule.
            sleep_seconds = min(120, 10 * (attempt + 1))
            if attempt < attempts - 1:
                time.sleep(sleep_seconds)
    raise RuntimeError(f"arXiv request failed after {attempts} attempts: {last_error}")


def text_of(entry: ET.Element, name: str) -> str:
    value = entry.findtext(f"atom:{name}", default="", namespaces=NS)
    return " ".join(value.split())


def parse_entries(raw: bytes, matched_keyword: dict[str, str]) -> list[dict[str, Any]]:
    root = ET.fromstring(raw)
    entries = []
    for entry in root.findall("atom:entry", NS):
        paper_id = text_of(entry, "id")
        links = entry.findall("atom:link", NS)
        pdf_url = ""
        for link in links:
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
                break
        authors = [
            " ".join((author.findtext("atom:name", default="", namespaces=NS) or "").split())
            for author in entry.findall("atom:author", NS)
        ]
        categories = [
            cat.attrib.get("term", "")
            for cat in entry.findall("atom:category", NS)
            if cat.attrib.get("term")
        ]
        entries.append({
            "id": paper_id,
            "title": text_of(entry, "title"),
            "summary": text_of(entry, "summary"),
            "published": text_of(entry, "published")[:10],
            "updated": text_of(entry, "updated")[:10],
            "authors": [a for a in authors if a],
            "categories": categories,
            "url": paper_id,
            "pdfUrl": pdf_url,
            "matchedKeywords": [matched_keyword["label"]],
            "matchedQueries": [matched_keyword["query"]],
            "firstSeenAt": utc_now(),
        })
    return entries


def merge_papers(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_id = {paper["id"]: paper for paper in existing if paper.get("id")}
    new_count = 0
    for paper in incoming:
        paper_id = paper.get("id")
        if not paper_id:
            continue
        if paper_id not in by_id:
            by_id[paper_id] = paper
            new_count += 1
            continue
        current = by_id[paper_id]
        for field in ("matchedKeywords", "matchedQueries"):
            merged = sorted(set(current.get(field, [])) | set(paper.get(field, [])))
            current[field] = merged
    papers = sorted(by_id.values(), key=lambda p: (p.get("published", ""), p.get("title", "")), reverse=True)
    return papers, new_count


def collect_once(args: argparse.Namespace) -> int:
    user_agent = os.getenv("ARXIV_USER_AGENT", DEFAULT_USER_AGENT)
    keywords = load_keywords(args.keyword_limit)
    cache = load_cache()
    papers = cache.get("papers", [])
    total_new = 0
    errors = []

    print(f"[{utc_now()}] arXiv collection: {len(keywords)} keywords, max_results={args.max_results}")
    print("Thank you to arXiv for use of its open access interoperability.")

    for index, keyword in enumerate(keywords, start=1):
        query = build_query(keyword["query"], tuple(args.categories))
        try:
            raw = fetch_arxiv(query, args.max_results, user_agent)
            incoming = parse_entries(raw, keyword)
            papers, new_count = merge_papers(papers, incoming)
            total_new += new_count
            print(f"  [{index:02d}/{len(keywords):02d}] +{new_count:02d} {keyword['label']}")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ET.ParseError, OSError) as exc:
            err = f"{keyword['label']}: {exc}"
            errors.append(err)
            print(f"  [{index:02d}/{len(keywords):02d}] ERROR {err}")

        if index < len(keywords):
            time.sleep(args.min_delay_seconds)

    cache["meta"].update({
        "source": "arXiv API",
        "generatedAt": utc_now(),
        "totalPapers": len(papers),
        "lastRunNewPapers": total_new,
        "lastRunErrors": errors,
        "categories": list(args.categories),
        "note": "Accumulated arXiv links collected by scripts/collect_arxiv.py.",
    })
    cache["papers"] = papers
    save_cache(cache)
    print(f"Wrote {LOCAL_OUTPUT_PATH} and {UI_OUTPUT_PATH}; new papers: {total_new}; total: {len(papers)}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect AI security papers from arXiv.")
    parser.add_argument("--watch", action="store_true", help="Run forever at the configured interval.")
    parser.add_argument("--interval-minutes", type=float, default=10.0, help="Watch interval in minutes.")
    parser.add_argument("--min-delay-seconds", type=float, default=3.5, help="Delay between arXiv requests.")
    parser.add_argument("--max-results", type=int, default=5, help="Recent results to inspect per keyword.")
    parser.add_argument("--keyword-limit", type=int, default=None, help="Limit keywords for testing.")
    parser.add_argument("--categories", nargs="+", default=list(DEFAULT_CATEGORIES), help="arXiv categories to include.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.watch:
        return collect_once(args)

    while True:
        collect_once(args)
        print(f"[{utc_now()}] Sleeping {args.interval_minutes} minutes before next arXiv run.")
        time.sleep(max(1, int(args.interval_minutes * 60)))


if __name__ == "__main__":
    raise SystemExit(main())
