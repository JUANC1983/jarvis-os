from __future__ import annotations

from typing import Any, Dict, List


class AccountingIntelligenceEngine:
    """
    Accounting / financial statement intelligence layer.
    """

    def analyze_financials(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        revenue = float(payload.get("revenue", 0))
        cogs = float(payload.get("cogs", 0))
        opex = float(payload.get("opex", 0))
        debt = float(payload.get("debt", 0))
        cash = float(payload.get("cash", 0))
        current_assets = float(payload.get("current_assets", 0))
        current_liabilities = float(payload.get("current_liabilities", 0))

        gross_profit = revenue - cogs
        ebitda_proxy = gross_profit - opex
        gross_margin = (gross_profit / revenue) * 100 if revenue else 0
        ebitda_margin = (ebitda_proxy / revenue) * 100 if revenue else 0
        current_ratio = (current_assets / current_liabilities) if current_liabilities else None
        net_debt = debt - cash

        alerts: List[str] = []
        if gross_margin < 20:
            alerts.append("Gross margin appears weak.")
        if ebitda_margin < 10:
            alerts.append("Operating profitability appears thin.")
        if current_ratio is not None and current_ratio < 1.0:
            alerts.append("Liquidity pressure may be present.")
        if net_debt > revenue * 0.5 and revenue > 0:
            alerts.append("Debt load may be high relative to revenue scale.")

        return {
            "gross_profit": round(gross_profit, 2),
            "ebitda_proxy": round(ebitda_proxy, 2),
            "gross_margin_pct": round(gross_margin, 2),
            "ebitda_margin_pct": round(ebitda_margin, 2),
            "net_debt": round(net_debt, 2),
            "current_ratio": round(current_ratio, 2) if current_ratio is not None else None,
            "alerts": alerts,
            "summary": "Accounting intelligence computed core profitability, liquidity, and leverage indicators.",
        }

    def accounting_policy_view(self, query: str) -> Dict[str, Any]:
        text = query.lower()
        references = []

        if any(w in text for w in ["ifrs", "niif", "ias"]):
            references.append("IFRS / NIIF reference required.")
        if any(w in text for w in ["revenue", "ingresos"]):
            references.append("Revenue recognition policy should be validated.")
        if any(w in text for w in ["lease", "arrendamiento"]):
            references.append("Lease treatment may require IFRS 16 / local standard review.")
        if any(w in text for w in ["financial instrument", "instrumento financiero", "credit loss"]):
            references.append("Financial instrument classification / impairment review may be required.")

        if not references:
            references.append("Validate applicable accounting framework and materiality thresholds.")

        return {
            "query": query,
            "policy_flags": references,
            "summary": "Accounting policy review generated reference flags.",
        }
