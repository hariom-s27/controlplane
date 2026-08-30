#!/usr/bin/env python3
"""
S2's gate condition, made runnable: docs/ROADMAP.md says run the negative-
control agent five times with different phrasings and confirm it proposes
the refund in the MAJORITY of runs, without the prompt telling it to.

    CP_MODE=live python scripts/gate_check.py

This check deliberately forces five fresh live calls. Replaying the two retired
empty fixtures would not test whether the explicit token budget fixed the bug.

If it fails: fix the retrieval, never the prompt. Do not add "you should
approve this refund" to make the number go up — that's the puppet show a
mentor will spot.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.servicing_agent import propose  # noqa: E402

PHRASINGS = [
    "hi, the blue running shoes I ordered arrived a while back "
    "but they don't fit at all — can I get a full refund?",
    "Hey, I bought some blue running shoes a few weeks ago and they're "
    "too small. I'd like a refund please.",
    "The blue running shoes I got don't fit right, wasn't a good fit at "
    "all. Can you refund me for them?",
    "So I ordered blue running shoes some time back and it turns out the "
    "sizing is off. Is a full refund possible?",
    "hii i got the blue runnin shoes but they dont fit me well at all, "
    "can u refund the full amount?",
]


def main() -> int:
    proposed = 0
    for i, phrasing in enumerate(PHRASINGS, start=1):
        call, message, _, _ = propose(phrasing, force_live=True)
        if call:
            proposed += 1
            print(f"[{i}] PROPOSED  {call['name']}({call['args']})", flush=True)
        else:
            note = (message.get("content") or "").strip()[:100]
            print(f"[{i}] NOTHING   {note or '(empty response)'}", flush=True)

    majority = proposed > len(PHRASINGS) / 2
    print(f"\n{proposed}/{len(PHRASINGS)} proposed a refund unprompted — "
          f"{'PASS' if majority else 'FAIL'} (need a majority)", flush=True)
    return 0 if majority else 1


if __name__ == "__main__":
    sys.exit(main())
