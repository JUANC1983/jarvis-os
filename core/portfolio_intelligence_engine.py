"""
Portfolio Intelligence Engine.

Analyzes a unified portfolio snapshot and returns institutional-grade
risk/opportunity insights. Language: Spanish-first. Tone: institutional.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


class PortfolioIntelligenceEngine:

    def analyze(self, portfolio: Dict) -> Dict:
        """
        Full portfolio intelligence analysis.

        Input: unified_portfolio snapshot (from UnifiedPortfolioEngine.build_snapshot)
        Output: intelligence report with score, risks, opportunities, paper trade ideas.
        """
        if not portfolio or portfolio.get("status") == "no_data":
            return self._no_data_report()

        positions    = portfolio.get("all_positions", [])
        total_value  = portfolio.get("total_market_value", 0)
        total_cash   = portfolio.get("total_cash", 0)
        daily_pnl    = portfolio.get("total_daily_pnl", 0)
        unrealized   = portfolio.get("total_unrealized_pnl", 0)
        sectors      = portfolio.get("sector_exposure", [])
        themes       = portfolio.get("theme_exposure", [])
        asset_classes = portfolio.get("asset_class_exposure", [])
        warnings     = portfolio.get("concentration_warnings", [])
        brokers      = portfolio.get("brokers", {})
        largest      = portfolio.get("largest_positions", [])

        total_portfolio = total_value + total_cash

        # ── Score components ──────────────────────────────────────────────────
        score = 50
        top_risks: List[str] = []
        opportunities: List[str] = []
        broker_obs: List[str] = []
        sector_warn: List[str] = []
        paper_ideas: List[str] = []
        do_not_touch: List[str] = []
        limitations: List[str] = []

        # Diversification score
        n_positions = len(positions)
        if n_positions == 0:
            score -= 30
            limitations.append("No positions detected — conecta un broker para análisis real")
        elif n_positions < 5:
            score -= 10
            top_risks.append(f"Portafolio muy concentrado: solo {n_positions} posiciones")
        elif n_positions > 30:
            score += 5
            opportunities.append("Buena diversificación por número de posiciones")
        elif n_positions >= 10:
            score += 8

        # Concentration risk
        for w in warnings:
            if w["type"] == "single_name_concentration":
                score -= 8
                sym = w["symbol"]
                pct = w["weight_pct"]
                top_risks.append(
                    f"{sym} representa el {pct}% del portafolio — riesgo de concentración de nombre único"
                )
                if pct > 30:
                    do_not_touch.append(f"{sym} — no aumentar hasta reducir concentración")
            elif w["type"] == "sector_concentration":
                score -= 6
                sector_warn.append(
                    f"Sector {w['sector']}: {w['pct']}% del portafolio — sobre-exposición sectorial"
                )

        # Cash ratio
        if total_portfolio > 0:
            cash_pct = total_cash / total_portfolio * 100
            if cash_pct > 40:
                score += 5
                opportunities.append(
                    f"Efectivo elevado ({cash_pct:.1f}%) — oportunidad de deployment gradual en activos de calidad"
                )
            elif cash_pct < 5:
                score -= 5
                top_risks.append(
                    f"Efectivo muy bajo ({cash_pct:.1f}%) — poca capacidad de reacción ante oportunidades o caídas"
                )

        # Daily P&L signal
        if total_value > 0:
            daily_pct = daily_pnl / total_value * 100
            if daily_pct < -3:
                score -= 8
                top_risks.append(
                    f"Día significativamente negativo: {daily_pct:.2f}% — revisar catalizadores"
                )
            elif daily_pct > 3:
                score += 3
            elif daily_pct < -1:
                top_risks.append(f"Movimiento diario negativo: {daily_pct:.2f}%")

        # Unrealized P&L health
        if total_value > 0:
            unr_pct = unrealized / total_value * 100
            if unr_pct < -10:
                score -= 10
                top_risks.append(
                    f"Pérdida no realizada elevada: {unr_pct:.1f}% — revisar tesis de inversión"
                )
            elif unr_pct > 15:
                score += 5
                opportunities.append(
                    f"Ganancia no realizada de {unr_pct:.1f}% — considerar toma parcial de utilidades"
                )

        # Sector balance
        top_sector = sectors[0] if sectors else None
        if top_sector and top_sector["pct"] > 50:
            sector_warn.append(
                f"Sector dominante: {top_sector['label']} con {top_sector['pct']}% del portafolio"
            )
        elif len(sectors) >= 4:
            score += 5
            opportunities.append(
                f"Exposición en {len(sectors)} sectores — diversificación sectorial adecuada"
            )

        # Crypto exposure check
        crypto_exposure = next((s for s in asset_classes if s["label"] == "crypto"), None)
        if crypto_exposure and crypto_exposure["pct"] > 20:
            top_risks.append(
                f"Cripto = {crypto_exposure['pct']}% del portafolio — alta volatilidad, riesgo de cola elevado"
            )
            score -= 5

        # Broker observations
        for broker_name, bdata in brokers.items():
            bval = bdata.get("market_value", 0)
            bstatus = bdata.get("status", "unknown")
            if bstatus in ("not_connected", "disconnected", "not_configured"):
                broker_obs.append(f"{broker_name.upper()}: no conectado — sin datos disponibles")
                limitations.append(f"Datos de {broker_name.upper()} no disponibles — resultados parciales")
            elif bdata.get("_stale"):
                broker_obs.append(
                    f"{broker_name.upper()}: mostrando datos cached — posiblemente desactualizados"
                )
                limitations.append(f"{broker_name.upper()} usa snapshot anterior — reconectar para datos en tiempo real")
            else:
                pct = bdata.get("market_value", 0) / total_value * 100 if total_value else 0
                broker_obs.append(
                    f"{broker_name.upper()}: ${bval:,.0f} ({pct:.1f}% del capital invertido)"
                )

        # Paper trade ideas
        if positions:
            worst = sorted(positions, key=lambda p: p.get("daily_pnl", 0))[:2]
            best  = sorted(positions, key=lambda p: p.get("daily_pnl", 0), reverse=True)[:2]
            for p in worst:
                if p.get("daily_pnl", 0) < -500:
                    paper_ideas.append(
                        f"Paper: Simular reducir {p['symbol']} — baja {p.get('daily_pnl_pct', 0):.1f}% hoy"
                    )
            for p in best:
                if p.get("daily_pnl", 0) > 300:
                    paper_ideas.append(
                        f"Paper: Simular toma de utilidades en {p['symbol']} — sube {p.get('daily_pnl_pct', 0):.1f}% hoy"
                    )

        if not paper_ideas and n_positions > 0:
            paper_ideas.append("Importa el portafolio al Paper Lab para simular escenarios de rebalanceo")

        # Final score clamp
        score = max(0, min(100, score))
        risk_level = (
            "critical" if score < 25 else
            "high"     if score < 45 else
            "medium"   if score < 65 else
            "low"
        )

        # Summary
        if n_positions == 0:
            summary = "No hay posiciones activas. Conecta IBKR o Hapi para análisis en tiempo real."
        else:
            daily_dir = "positivo" if daily_pnl >= 0 else "negativo"
            summary = (
                f"Portafolio de ${total_portfolio:,.0f} ({n_positions} posiciones). "
                f"P&L diario {daily_dir}: ${daily_pnl:+,.0f}. "
                f"Ganancia/pérdida no realizada: ${unrealized:+,.0f}. "
                f"Score de riesgo: {score}/100 ({risk_level.upper()})."
            )

        return {
            "portfolio_score":       score,
            "risk_level":            risk_level,
            "summary":               summary,
            "top_risks":             top_risks[:6],
            "opportunities":         opportunities[:5],
            "broker_observations":   broker_obs,
            "sector_warnings":       sector_warn[:4],
            "paper_trade_ideas":     paper_ideas[:5],
            "do_not_touch":          do_not_touch[:5],
            "confidence":            75 if not limitations else 45,
            "limitations":           limitations,
            "generated_at":          datetime.utcnow().isoformat(),
        }

    # ── Legacy method (backward compat) ───────────────────────────────────────

    def analyze_legacy(self, portfolio: Dict) -> Dict:
        """Original 23-line sector analysis — kept for backward compatibility."""
        assets = portfolio.get("assets", [])
        exposures: Dict[str, float] = {}
        for asset in assets:
            sector = asset.get("sector", "unknown")
            exposures.setdefault(sector, 0)
            exposures[sector] += asset.get("value", 0)
        total = sum(exposures.values())
        allocation = {}
        if total > 0:
            for k, v in exposures.items():
                allocation[k] = round((v / total) * 100, 2)
        return {
            "allocation":  allocation,
            "total_value": total,
            "insight":     "Portfolio exposure analysis complete",
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _no_data_report(self) -> Dict:
        return {
            "portfolio_score":      0,
            "risk_level":           "unknown",
            "summary":              "Sin datos de portafolio. Conecta IBKR o Hapi para activar el análisis.",
            "top_risks":            ["No hay datos de broker disponibles"],
            "opportunities":        [],
            "broker_observations":  [],
            "sector_warnings":      [],
            "paper_trade_ideas":    ["Usa el Paper Lab para simular con datos de referencia"],
            "do_not_touch":         [],
            "confidence":           0,
            "limitations":          ["Ningún broker conectado — datos de portfolio no disponibles"],
            "generated_at":         datetime.utcnow().isoformat(),
            "real_trade":           False,
        }


# Singleton
portfolio_intelligence = PortfolioIntelligenceEngine()
