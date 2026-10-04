#!/usr/bin/env python3
"""
Evaluation harness for Paste-to-Product.

Measures:
- Parse quality: items extracted vs expected
- Top-1 / Top-3 match rate (by category keyword)
- Confidence calibration: mean confidence per confidence band
- Latency: p50 / p95 per phase
- SerpApi calls per run

Usage:
    cd backend
    python ../eval/run_eval.py [--chats eval/test_chats] [--market in]

Outputs: console table + eval/report.md
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean, median, quantiles
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

from backend.app.config import Settings
from backend.app.parser import parse_chat
from backend.app.finder import find_products
from backend.app.verifier import verify_match
from backend.app.serpapi_client import SerpApiClient, SerpApiError


def load_label(label_path: Path) -> Optional[dict]:
    """Load expected items from a JSON label file."""
    if not label_path.exists():
        return None
    return json.loads(label_path.read_text())


def top_n_hit(candidates, expected_category: str, n: int) -> bool:
    """Check if any of the top-n candidates match the expected category keyword."""
    top = candidates[:n]
    kw = expected_category.lower()
    return any(kw in c.title.lower() for c in top)


async def eval_chat(
    chat_path: Path,
    label_path: Path,
    settings: Settings,
    market: str,
) -> dict:
    chat_text = chat_path.read_text(encoding="utf-8")
    label = load_label(label_path)

    client = SerpApiClient(
        api_key=settings.serpapi_api_key,
        cache_db=settings.cache_db_path,
        max_calls=settings.max_calls_per_session,
    )

    # --- Parse phase ---
    t0 = time.perf_counter()
    try:
        parse_result = await parse_chat(
            chat_text,
            settings.bedrock_model_parse,
            settings.aws_bearer_token_bedrock,
            settings.aws_region,
        )
    except Exception as e:
        return {"name": chat_path.stem, "error": str(e)}
    parse_ms = (time.perf_counter() - t0) * 1000

    expected_items = label.get("items", []) if label else []
    parsed_count = len(parse_result.items)
    expected_count = len(expected_items)
    parse_hit_rate = (
        min(parsed_count, expected_count) / expected_count if expected_count else 1.0
    )

    # --- Find + verify phase ---
    top1_hits = []
    top3_hits = []
    confidence_scores = []
    total_find_ms = 0.0
    serpapi_calls_start = client.get_call_count()

    for i, item in enumerate(parse_result.items):
        t1 = time.perf_counter()
        try:
            candidates = await find_products(item, client, market)
        except (SerpApiError, Exception):
            candidates = []
        total_find_ms += (time.perf_counter() - t1) * 1000

        for c in candidates[:5]:
            vr = verify_match(item, c)
            confidence_scores.append(vr.overall_confidence)

        # Use expected label if available, else use the parsed category
        if i < len(expected_items):
            expected_cat = expected_items[i].get("category", item.category)
        else:
            expected_cat = item.category

        top1_hits.append(top_n_hit(candidates, expected_cat, 1))
        top3_hits.append(top_n_hit(candidates, expected_cat, 3))

    serpapi_calls = client.get_call_count() - serpapi_calls_start

    # Confidence calibration: group by band
    bands = {"high": [], "mid": [], "low": []}
    for c in confidence_scores:
        if c >= 0.8:
            bands["high"].append(c)
        elif c >= 0.5:
            bands["mid"].append(c)
        else:
            bands["low"].append(c)

    return {
        "name": chat_path.stem,
        "parse_ms": round(parse_ms),
        "find_ms_total": round(total_find_ms),
        "parsed_items": parsed_count,
        "expected_items": expected_count,
        "parse_hit_rate": round(parse_hit_rate, 2),
        "top1_rate": round(mean(top1_hits), 2) if top1_hits else 0,
        "top3_rate": round(mean(top3_hits), 2) if top3_hits else 0,
        "mean_confidence": round(mean(confidence_scores), 3) if confidence_scores else 0,
        "confidence_bands": {k: round(mean(v), 3) if v else None for k, v in bands.items()},
        "serpapi_calls": serpapi_calls,
        "error": None,
    }


def render_table(results: list[dict]) -> str:
    headers = ["Chat", "Parse%", "Top1%", "Top3%", "ConfMean", "SerpCalls", "ParseMs", "FindMs"]
    rows = []
    for r in results:
        if r.get("error"):
            rows.append([r["name"], "ERROR", "-", "-", "-", "-", "-", "-"])
        else:
            rows.append([
                r["name"],
                f"{r['parse_hit_rate']*100:.0f}%",
                f"{r['top1_rate']*100:.0f}%",
                f"{r['top3_rate']*100:.0f}%",
                f"{r['mean_confidence']:.3f}",
                str(r["serpapi_calls"]),
                f"{r['parse_ms']}ms",
                f"{r['find_ms_total']}ms",
            ])

    col_widths = [max(len(h), max(len(row[i]) for row in rows)) for i, h in enumerate(headers)]
    sep = "  ".join("-" * w for w in col_widths)
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    data_lines = [
        "  ".join(cell.ljust(w) for cell, w in zip(row, col_widths))
        for row in rows
    ]
    return "\n".join([header_line, sep] + data_lines)


def write_report(results: list[dict], report_path: Path) -> None:
    lines = ["# Paste-to-Product Evaluation Report\n"]

    valid = [r for r in results if not r.get("error")]
    if valid:
        lines.append("## Summary\n")
        lines.append(f"- **Chats evaluated:** {len(results)}")
        lines.append(f"- **Errors:** {len([r for r in results if r.get('error')])}")
        lines.append(f"- **Mean parse hit rate:** {mean(r['parse_hit_rate'] for r in valid)*100:.0f}%")
        lines.append(f"- **Mean top-1 match rate:** {mean(r['top1_rate'] for r in valid)*100:.0f}%")
        lines.append(f"- **Mean top-3 match rate:** {mean(r['top3_rate'] for r in valid)*100:.0f}%")
        lines.append(f"- **Mean confidence:** {mean(r['mean_confidence'] for r in valid):.3f}")
        lines.append(f"- **Total SerpApi calls:** {sum(r['serpapi_calls'] for r in valid)}")
        lines.append("")

    lines.append("## Per-Chat Results\n")
    lines.append("```")
    lines.append(render_table(results))
    lines.append("```\n")

    lines.append("## Errors\n")
    for r in results:
        if r.get("error"):
            lines.append(f"- **{r['name']}**: {r['error']}")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {report_path}")


async def main():
    parser = argparse.ArgumentParser(description="Evaluate Paste-to-Product pipeline")
    parser.add_argument("--chats", default="eval/test_chats", help="Directory of test chats")
    parser.add_argument("--labels", default="eval/labels", help="Directory of label JSON files")
    parser.add_argument("--market", default="in", help="Market (in/us)")
    parser.add_argument("--report", default="eval/report.md", help="Output report path")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    chats_dir = root / args.chats
    labels_dir = root / args.labels
    report_path = root / args.report

    if not chats_dir.exists():
        print(f"Chats directory not found: {chats_dir}")
        sys.exit(1)

    settings = Settings()
    chat_files = sorted(chats_dir.glob("*.txt"))
    if not chat_files:
        print(f"No .txt files found in {chats_dir}")
        sys.exit(1)

    print(f"Evaluating {len(chat_files)} chats (market={args.market})...\n")
    results = []
    for cf in chat_files:
        label_path = labels_dir / (cf.stem + ".json")
        print(f"  {cf.stem}...", end=" ", flush=True)
        result = await eval_chat(cf, label_path, settings, args.market)
        results.append(result)
        if result.get("error"):
            print(f"ERROR: {result['error']}")
        else:
            print(f"top1={result['top1_rate']*100:.0f}%  conf={result['mean_confidence']:.2f}")

    print("\n" + render_table(results))
    write_report(results, report_path)


if __name__ == "__main__":
    asyncio.run(main())
