"""Deterministic mock-data helpers for connector providers.

Mock providers must be *deterministic* (same entity → same data) so tests and
demos are reproducible, yet *realistic* enough to exercise downstream analytics.
Everything here is seeded from the entity reference via a stable hash, so a given
GSTIN/CIN/PAN always yields the same synthetic company, statements and bureau
report.
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta
from typing import List, Tuple


def seed_for(*parts: str) -> int:
    """A stable 63-bit seed derived from the given string parts."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def rng_for(*parts: str) -> random.Random:
    return random.Random(seed_for(*parts))


_STATES = [
    ("27", "Maharashtra"), ("07", "Delhi"), ("29", "Karnataka"),
    ("33", "Tamil Nadu"), ("24", "Gujarat"), ("36", "Telangana"),
    ("19", "West Bengal"), ("09", "Uttar Pradesh"),
]
_CITIES = ["Mumbai", "Pune", "Bengaluru", "Chennai", "Ahmedabad", "Hyderabad", "Kolkata", "Noida"]
_INDUSTRIES = [
    "Manufacturing", "Trading", "IT Services", "Textiles", "Pharmaceuticals",
    "Logistics", "Retail", "Construction", "Food Processing", "Auto Components",
]
_SUFFIXES = ["Enterprises", "Industries", "Trading Co", "Technologies", "Exports",
             "Solutions", "Manufacturing", "Retail", "Logistics"]
_FIRST = ["Sharma", "Patel", "Reddy", "Iyer", "Gupta", "Khan", "Nair", "Verma", "Bose", "Rao"]
_GIVEN = ["Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anita", "Suresh", "Deepa", "Arjun", "Kavya"]


def company_name(rng: random.Random) -> str:
    return f"{rng.choice(_GIVEN)} {rng.choice(_SUFFIXES)}"


def person_name(rng: random.Random) -> str:
    return f"{rng.choice(_GIVEN)} {rng.choice(_FIRST)}"


def state_code(rng: random.Random) -> Tuple[str, str]:
    return rng.choice(_STATES)


def city(rng: random.Random) -> str:
    return rng.choice(_CITIES)


def industry(rng: random.Random) -> str:
    return rng.choice(_INDUSTRIES)


def make_gstin(rng: random.Random) -> str:
    sc, _ = state_code(rng)
    pan = make_pan(rng)
    return f"{sc}{pan}{rng.randint(1, 9)}Z{rng.randint(0, 9)}"


def make_pan(rng: random.Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(5))
    digits = "".join(str(rng.randint(0, 9)) for _ in range(4))
    return f"{letters}{digits}{rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"


def make_cin(rng: random.Random) -> str:
    sc, _ = state_code(rng)
    return (
        f"U{rng.randint(10000, 99999)}{['MH','DL','KA','TN','GJ'][rng.randint(0,4)]}"
        f"{rng.randint(1995, 2022)}PTC{rng.randint(100000, 999999)}"
    )


def month_starts(count: int, end: date) -> List[date]:
    """Return ``count`` month-start dates ending at the month of ``end`` (oldest first)."""
    out: List[date] = []
    y, m = end.year, end.month
    for _ in range(count):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def iso(dt: date) -> str:
    return dt.isoformat()


def now_utc() -> datetime:
    return datetime.utcnow()


def days_ago(n: int) -> datetime:
    return datetime.utcnow() - timedelta(days=n)
