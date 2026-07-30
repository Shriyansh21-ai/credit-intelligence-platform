"""Pure, dependency-free financial mathematics shared across Track 3.

Nothing in this module touches the database, the network or any LLM. Everything
here is deterministic and safe to import from migrations, tests and services
alike — mirroring the ``services/autonomous/common.py`` and
``services/ai_platform/common.py`` conventions from Phase 9 and Track 2.

The Track 3 Advanced Financial Intelligence Platform is a *quantitative* layer,
so the primitives here are richer than the earlier tracks: time-value-of-money,
statistics, distributions, a seedable deterministic RNG (for reproducible Monte
Carlo without ``random``/``numpy``), interpolation, matrix helpers and the
regulatory building blocks (PD/LGD/EAD → ECL) reused by several milestones.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    """Timezone-naive UTC now (matches the rest of the codebase's DateTime cols)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


# ---------------------------------------------------------------------------
# Numeric primitives
# ---------------------------------------------------------------------------

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def safe_div(numerator: float, denominator: float, default: Optional[float] = None) -> Optional[float]:
    if not denominator:
        return default
    return numerator / denominator


def round_opt(value: Optional[float], ndigits: int = 4) -> Optional[float]:
    return round(value, ndigits) if value is not None else None


def pct(value: Optional[float], ndigits: int = 2) -> Optional[float]:
    """Return a fraction as a percentage rounded for presentation."""
    return round(value * 100.0, ndigits) if value is not None else None


def bps(value: Optional[float]) -> Optional[float]:
    """Fraction -> basis points."""
    return round(value * 10000.0, 2) if value is not None else None


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------

def mean(xs: Sequence[float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def variance(xs: Sequence[float], sample: bool = True) -> float:
    xs = list(xs)
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    denom = (n - 1) if sample else n
    return sum((x - m) ** 2 for x in xs) / denom


def stdev(xs: Sequence[float], sample: bool = True) -> float:
    return math.sqrt(variance(xs, sample=sample))


def covariance(xs: Sequence[float], ys: Sequence[float], sample: bool = True) -> float:
    xs, ys = list(xs), list(ys)
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    mx, my = mean(xs[:n]), mean(ys[:n])
    denom = (n - 1) if sample else n
    return sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / denom


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    sx, sy = stdev(xs), stdev(ys)
    if sx == 0 or sy == 0:
        return 0.0
    return clamp(covariance(xs, ys) / (sx * sy), -1.0, 1.0)


def percentile(xs: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile, ``q`` in [0, 100]. Empty -> 0.0."""
    data = sorted(xs)
    if not data:
        return 0.0
    if len(data) == 1:
        return float(data[0])
    rank = clamp(q / 100.0, 0.0, 1.0) * (len(data) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(data[lo])
    frac = rank - lo
    return float(data[lo] * (1 - frac) + data[hi] * frac)


def herfindahl(weights: Sequence[float]) -> float:
    """Herfindahl-Hirschman Index of a weight vector (sum of squared shares).

    Weights need not be normalized; they are normalized to sum 1 first. 1.0 is a
    single fully-concentrated position, ~1/N is perfectly diversified.
    """
    total = sum(abs(w) for w in weights)
    if total <= 0:
        return 0.0
    shares = [abs(w) / total for w in weights]
    return sum(s * s for s in shares)


def gini(values: Sequence[float]) -> float:
    """Gini coefficient of a non-negative exposure/size vector (0 even, →1 concentrated)."""
    xs = sorted(abs(v) for v in values)
    n = len(xs)
    s = sum(xs)
    if n == 0 or s == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2.0 * cum) / (n * s) - (n + 1.0) / n


# ---------------------------------------------------------------------------
# Normal distribution (pure — no scipy)
# ---------------------------------------------------------------------------

def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def norm_cdf(x: float) -> float:
    """Standard-normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation)."""
    p = clamp(p, 1e-12, 1.0 - 1e-12)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# ---------------------------------------------------------------------------
# Deterministic RNG — reproducible Monte Carlo without external deps.
# ---------------------------------------------------------------------------

class DeterministicRNG:
    """A small, seedable PRNG (SplitMix64) yielding reproducible uniforms/normals.

    Deterministic and stdlib-only so Monte Carlo simulations are exactly
    repeatable across machines and test runs (no ``random``/``numpy``).
    """

    _MASK = (1 << 64) - 1

    def __init__(self, seed: Any = 0):
        if isinstance(seed, str):
            seed = int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
        self._state = int(seed) & self._MASK

    def _next_u64(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & self._MASK
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self._MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self._MASK
        return (z ^ (z >> 31)) & self._MASK

    def random(self) -> float:
        """Uniform in [0, 1)."""
        return self._next_u64() / (1 << 64)

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.random()

    def normal(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        return mu + sigma * norm_ppf(self.random())

    def normals(self, n: int, mu: float = 0.0, sigma: float = 1.0) -> List[float]:
        return [self.normal(mu, sigma) for _ in range(n)]


# ---------------------------------------------------------------------------
# Time value of money
# ---------------------------------------------------------------------------

def present_value(cashflows: Sequence[float], rate: float, times: Optional[Sequence[float]] = None) -> float:
    """PV of ``cashflows`` discounted at a flat ``rate`` (per period)."""
    if times is None:
        times = range(len(cashflows))
    return sum(cf / ((1.0 + rate) ** t) for cf, t in zip(cashflows, times))


def npv(rate: float, cashflows: Sequence[float]) -> float:
    """NPV where ``cashflows[0]`` occurs at t=0."""
    return sum(cf / ((1.0 + rate) ** t) for t, cf in enumerate(cashflows))


def irr(cashflows: Sequence[float], guess: float = 0.1, iterations: int = 200) -> Optional[float]:
    """Internal rate of return via bisection on a sign-bracketed interval."""
    cashflows = list(cashflows)
    if not cashflows or all(c >= 0 for c in cashflows) or all(c <= 0 for c in cashflows):
        return None
    lo, hi = -0.9999, 10.0
    f_lo = npv(lo, cashflows)
    f_hi = npv(hi, cashflows)
    if f_lo * f_hi > 0:
        return None
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid, cashflows)
        if abs(f_mid) < 1e-9:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def annuity_payment(principal: float, rate: float, periods: int) -> float:
    """Level payment amortizing ``principal`` at ``rate`` over ``periods``."""
    if periods <= 0:
        return 0.0
    if rate == 0:
        return principal / periods
    return principal * rate / (1.0 - (1.0 + rate) ** (-periods))


def cagr(begin: float, end: float, years: float) -> Optional[float]:
    if begin <= 0 or years <= 0:
        return None
    return (end / begin) ** (1.0 / years) - 1.0


# ---------------------------------------------------------------------------
# Interpolation (yield curves, term structures)
# ---------------------------------------------------------------------------

def linear_interp(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    """Piecewise-linear interpolation with flat extrapolation at the ends."""
    pts = sorted(zip(xs, ys))
    if not pts:
        return 0.0
    if x <= pts[0][0]:
        return float(pts[0][1])
    if x >= pts[-1][0]:
        return float(pts[-1][1])
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        if x0 <= x <= x1:
            if x1 == x0:
                return float(y0)
            frac = (x - x0) / (x1 - x0)
            return float(y0 + frac * (y1 - y0))
    return float(pts[-1][1])


# ---------------------------------------------------------------------------
# Regulatory building blocks (PD/LGD/EAD → ECL) — shared by M2, M3, M8, M9.
# ---------------------------------------------------------------------------

# Rating -> through-the-cycle PD (12m). Deterministic, explainable master scale.
RATING_PD: Dict[str, float] = {
    "AAA": 0.0003, "AA": 0.0008, "A": 0.0025, "BBB": 0.0075,
    "BB": 0.0200, "B": 0.0600, "CCC": 0.1800, "CC": 0.3000,
    "C": 0.4500, "D": 1.0000,
}
RATING_ORDER: List[str] = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]


def pd_from_score(score: Optional[float]) -> float:
    """Map a 300-900 enterprise credit score to a 12-month PD (logistic)."""
    if score is None:
        return 0.05
    s = clamp((score - 300) / 600.0, 0.0, 1.0)
    # Higher score -> lower PD; anchored roughly to the master scale.
    return round(clamp(0.35 * math.exp(-4.0 * s), 0.0003, 0.9999), 6)


def rating_from_pd(pd: float) -> str:
    for r in RATING_ORDER:
        if pd <= RATING_PD[r]:
            return r
    return "D"


def expected_loss(pd: float, lgd: float, ead: float) -> float:
    """EL = PD × LGD × EAD."""
    return clamp(pd, 0.0, 1.0) * clamp(lgd, 0.0, 1.0) * max(ead, 0.0)


def unexpected_loss(pd: float, lgd: float, ead: float) -> float:
    """Single-name unexpected loss (std-dev of default loss), Basel-style.

    UL = EAD × LGD × sqrt(PD × (1 − PD)).
    """
    pd = clamp(pd, 0.0, 1.0)
    return max(ead, 0.0) * clamp(lgd, 0.0, 1.0) * math.sqrt(pd * (1.0 - pd))


def marginal_pd_curve(pd_12m: float, horizon_years: int) -> List[float]:
    """Simple survival-based marginal PD term structure for lifetime ECL."""
    pd_12m = clamp(pd_12m, 0.0, 0.9999)
    survival = 1.0
    out: List[float] = []
    for _ in range(max(horizon_years, 1)):
        marginal = survival * pd_12m
        out.append(marginal)
        survival *= (1.0 - pd_12m)
    return out


# ---------------------------------------------------------------------------
# Hashing / identity (content addressing & reproducibility)
# ---------------------------------------------------------------------------

def checksum(obj: Any) -> str:
    """Stable SHA-256 over a JSON-serialisable object (sorted keys)."""
    import json
    payload = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def stable_id(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Grounding — every AI narrative in Track 3 phrases *these* deterministic facts.
# ---------------------------------------------------------------------------

def grounding_block(title: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """Package deterministic facts + a checksum so narratives stay auditable."""
    return {"title": title, "facts": facts, "checksum": checksum(facts),
            "generated_at": iso(utcnow())}


def weighted_average(pairs: Iterable[Tuple[float, float]]) -> Optional[float]:
    """Weighted mean of (value, weight) pairs."""
    num = 0.0
    den = 0.0
    for value, weight in pairs:
        num += value * weight
        den += weight
    return safe_div(num, den)


def normalize(weights: Sequence[float]) -> List[float]:
    total = sum(abs(w) for w in weights)
    if total <= 0:
        return [0.0 for _ in weights]
    return [w / total for w in weights]
