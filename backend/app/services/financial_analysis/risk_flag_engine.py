"""Financial Risk Flag Engine (Task 5).

Deterministically detects adverse financial conditions. Each flag carries a
``severity``, a ``reason`` (why it fired, with the driving numbers) and a
``recommendation``. Rules only fire when their inputs are present, so a sparse
statement produces fewer flags rather than false positives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Mapping

from .ratio_engine import Ratio
from .statement import FinancialStatement

CRITICAL = "critical"
HIGH = "high"
MEDIUM = "medium"
LOW = "low"

_SEVERITY_RANK = {CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3}


@dataclass
class RiskFlag:
    code: str
    title: str
    severity: str
    reason: str
    recommendation: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "severity": self.severity,
            "reason": self.reason,
            "recommendation": self.recommendation,
        }


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def detect_risk_flags(
    statement: FinancialStatement,
    ratios: Mapping[str, Ratio],
) -> List[RiskFlag]:
    s = statement
    flags: List[RiskFlag] = []

    def val(key: str):
        r = ratios.get(key)
        return r.value if r else None

    # -- Negative / non-positive equity (checked first: it suppresses D/E, ROE)
    if s.total_equity is not None and s.total_equity <= 0:
        flags.append(RiskFlag(
            "negative_equity", "Negative net worth", CRITICAL,
            f"Total equity is {s.total_equity:,.0f}, meaning liabilities exceed assets.",
            "Recapitalise the business; do not extend unsecured credit until equity is restored.",
        ))

    # -- Negative working capital
    wc = s.working_capital
    if wc is not None and wc < 0:
        flags.append(RiskFlag(
            "negative_working_capital", "Negative working capital", HIGH,
            f"Current liabilities exceed current assets by {abs(wc):,.0f}.",
            "Strengthen working capital via longer payables, faster collections or a WC facility.",
        ))

    # -- Low liquidity
    cr = val("current_ratio")
    if cr is not None and cr < 1.0:
        flags.append(RiskFlag(
            "low_liquidity", "Low liquidity", HIGH,
            f"Current ratio is {cr:.2f}x (< 1.0x): short-term assets do not cover short-term dues.",
            "Build a liquidity buffer before drawing new short-term debt.",
        ))

    # -- High leverage (debt ratio) and high debt (D/E)
    dr = val("debt_ratio")
    if dr is not None and dr > 0.8:
        flags.append(RiskFlag(
            "high_leverage", "High balance-sheet leverage", HIGH,
            f"Debt funds {_pct(dr)} of assets (> 80%), leaving a thin equity cushion.",
            "Reduce debt or inject equity to lower balance-sheet leverage.",
        ))
    de = val("debt_to_equity")
    if de is not None and de > 2.0:
        flags.append(RiskFlag(
            "high_debt", "High debt-to-equity", HIGH if de > 3.0 else MEDIUM,
            f"Debt-to-equity is {de:.2f}x, above the 2.0x comfort threshold.",
            "Deleverage or raise equity before adding further debt.",
        ))

    # -- Low interest coverage
    ic = val("interest_coverage")
    if ic is not None and ic < 1.5:
        flags.append(RiskFlag(
            "low_interest_coverage", "Low interest coverage", HIGH if ic < 1.0 else MEDIUM,
            f"EBIT covers interest only {ic:.2f}x (< 1.5x): earnings barely service interest.",
            "Improve operating earnings or refinance to reduce interest burden.",
        ))

    # -- Low DSCR
    dscr = val("dscr")
    if dscr is not None and dscr < 1.25:
        flags.append(RiskFlag(
            "low_dscr", "Weak debt-service coverage", HIGH if dscr < 1.0 else MEDIUM,
            f"DSCR is {dscr:.2f}x (< 1.25x): cash earnings are tight against total debt service.",
            "Right-size debt to a serviceable level; extend tenor to lower annual service.",
        ))

    # -- Poor profitability
    nm = val("net_margin")
    if nm is not None and nm < 0:
        flags.append(RiskFlag(
            "operating_loss", "Operating at a net loss", HIGH,
            f"Net margin is {_pct(nm)}: the business is loss-making.",
            "Restore profitability through pricing, cost control or revenue growth.",
        ))
    elif nm is not None and nm < 0.03:
        flags.append(RiskFlag(
            "poor_profitability", "Thin profitability", MEDIUM,
            f"Net margin is only {_pct(nm)} (< 3%), leaving little buffer for shocks.",
            "Improve margins before increasing fixed financial commitments.",
        ))

    # -- Cash flow deficit
    if s.operating_cash_flow is not None and s.operating_cash_flow < 0:
        flags.append(RiskFlag(
            "cash_flow_deficit", "Operating cash-flow deficit", HIGH,
            f"Operating cash flow is negative ({s.operating_cash_flow:,.0f}).",
            "Address the cash conversion cycle; negative operating cash flow is unsustainable.",
        ))
    if s.free_cash_flow_value is not None and s.free_cash_flow_value < 0:
        flags.append(RiskFlag(
            "negative_fcf", "Negative free cash flow", MEDIUM,
            f"Free cash flow is negative ({s.free_cash_flow_value:,.0f}) after reinvestment.",
            "Curb capex or lift operating cash flow to reach self-funding.",
        ))

    # -- Unusual expense ratios
    if s.revenue not in (None, 0):
        if s.operating_expenses is not None:
            opex_ratio = s.operating_expenses / s.revenue
            if opex_ratio > 0.6:
                flags.append(RiskFlag(
                    "high_opex", "Elevated operating expense ratio", MEDIUM,
                    f"Operating expenses are {_pct(opex_ratio)} of revenue (> 60%).",
                    "Review the cost base for structural inefficiencies.",
                ))
        cogs = s.cost_of_goods_sold
        if cogs is not None and cogs / s.revenue > 0.9:
            flags.append(RiskFlag(
                "high_cogs", "Very high cost of goods sold", MEDIUM,
                f"COGS is {_pct(cogs / s.revenue)} of revenue (> 90%), compressing gross margin.",
                "Renegotiate input costs or reprice to protect gross margin.",
            ))

    flags.sort(key=lambda f: _SEVERITY_RANK.get(f.severity, 9))
    return flags
