"""The one place money gets formatted for a human. R2.

Everywhere else in the pipeline amount_paise stays an integer. Never float,
never divided, until it reaches this function.
"""

from __future__ import annotations


def to_rupees(paise: int) -> str:
    return f"₹{paise // 100:,}"


__all__ = ["to_rupees"]
