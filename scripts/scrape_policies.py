#!/usr/bin/env python3
"""
S1 — one-off Firecrawl scrape of real, published retailer returns policies.

    pip install firecrawl-py   # commented out in requirements.txt until you run this
    FIRECRAWL_API_KEY=<key> CP_USE_FIRECRAWL=1 python scripts/scrape_policies.py

Writes data/seed/policies_raw.json and COMMIT that file. Once it's committed,
set CP_USE_FIRECRAWL=0 again — nothing else in the repo needs Firecrawl, and
the build stays offline-reproducible for anyone who clones it.

This buys one README sentence, ROADMAP.md's own words for it:

    "The policy corpus is scraped from real published returns policies.
     Only the version history is synthetic."

That is what turns data/seed/clauses.json from a made-up policy into a
synthetic version *history* layered on a real one — and it's the difference
this script exists to make true. Right now clauses.json's own `_note` field
says the text is still hand-authored placeholder; that note should be
deleted once you've reconciled it with what actually gets scraped here.

NOT RUN YET. I have no network access from this environment and did not
verify these three URLs resolve or that this firecrawl-py call shape matches
the SDK version pip installs today — check both when you run it. If a URL
is dead or JS-renders empty, ROADMAP.md's own fallback applies: try the
others, and if fewer than 2 succeed, keep the hand-authored text and say so
in the README instead of spending hours chasing a scrape.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from agents.llm import call_with_key_fallback, numbered_keys  # noqa: E402

OUT = ROOT / "data" / "seed" / "policies_raw.json"


def _firecrawl_is_retryable(exc: Exception) -> bool:
    """firecrawl-py raises its own UnauthorizedError (not an HTTP-status-
    code-bearing exception the way openai's SDK does) for a bad or
    out-of-credit key — matched by class name so this doesn't depend on
    firecrawl-py's exact module path, which has moved before (see the
    v1-vs-v4 call-shape note above)."""
    name = type(exc).__name__
    return name in ("UnauthorizedError", "PaymentRequiredError", "ForbiddenError", "RateLimitError") or \
        getattr(exc, "status_code", None) in (401, 402, 403, 429)

# Verify each of these actually resolves to a real returns/refund policy page
# before relying on the output — retailers restructure these URLs often, and
# this list was picked for being well-known, not for being checked live.
URLS = [
    "https://www.flipkart.com/pages/returnpolicy",
    "https://www.amazon.in/gp/help/customer/display.html?nodeId=GKM69DUUYKQWKWX7",
    "https://www.myntra.com/returnpolicy",
]


def main() -> int:
    if os.environ.get("CP_USE_FIRECRAWL", "0") != "1":
        print("CP_USE_FIRECRAWL != 1 — refusing to spend Firecrawl credits. Set it to 1 and retry.")
        return 1

    keys = numbered_keys("FIRECRAWL_API_KEY")
    if not keys:
        print("FIRECRAWL_API_KEY is not set.")
        return 1
    if len(keys) > 1:
        print(f"{len(keys)} FIRECRAWL_API_KEY* configured — will fall back through them "
              "in order if one is invalid or out of credit.\n")

    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        print("firecrawl-py is not installed. pip install firecrawl-py (it's in requirements.txt).")
        return 1

    results = []

    for url in URLS:
        print(f"scraping {url} ...")

        def _scrape(key: str, url: str = url):
            # firecrawl-py v4's FirecrawlClient.scrape() takes `formats`
            # directly — no `params={...}` wrapper, that was the v1-era shape.
            return FirecrawlApp(api_key=key).scrape(url, formats=["markdown"])

        try:
            resp = call_with_key_fallback("FIRECRAWL_API_KEY", _scrape, is_retryable=_firecrawl_is_retryable)
            markdown = resp.get("markdown") if isinstance(resp, dict) else getattr(resp, "markdown", None)
            if not markdown:
                print(f"  WARN  empty content from {url} — likely JS-rendered, skipping")
                continue
            results.append(
                {
                    "url": url,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "markdown": markdown,
                }
            )
            print(f"  ok  {len(markdown)} chars")
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL  {type(e).__name__}: {e}"
                  + (f"  (all {len(keys)} configured keys failed)" if len(keys) > 1 else ""))

    if len(results) < 2:
        print()
        print(f"Only {len(results)}/{len(URLS)} succeeded. ROADMAP.md's own fallback: "
              "keep the hand-authored clause text and say so in the README instead of "
              "chasing more sites.")
        if not results:
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT} ({len(results)} pages). Commit this file, then set CP_USE_FIRECRAWL=0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
