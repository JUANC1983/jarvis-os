from __future__ import annotations

import importlib
import traceback
from datetime import datetime
from typing import Any, Dict, Optional


class TaskExecutor:
    """
    Premium execution layer for JARVIS.
    - Centralizes all agent execution
    - Preserves memory and audit trail
    - Uses graceful fallbacks when some modules are missing
    - Keeps responses operational and structured
    """

    def __init__(self):
        self.memory = self._safe_instance("core.super_memory_system", "SuperMemorySystem")
        self.audit = self._safe_instance("core.audit_engine", "AuditEngine")
        self.conversation = self._safe_instance("core.conversation_engine", "ConversationEngine")

        self.ticker_resolver = self._safe_instance("core.ticker_resolver", "TickerResolver")
        self.trader = self._safe_instance("core.trader_alpha_engine", "TraderAlphaEngine")

        self.computer = self._safe_instance("core.computer_control_agent", "ComputerControlAgent")
        self.linkedin = self._safe_instance("core.linkedin_job_agent", "LinkedinJobAgent")
        self.image = self._safe_instance("core.image_generation_engine", "ImageGenerationEngine")
        self.video = self._safe_instance("core.video_analysis_engine", "VideoAnalysisEngine")

        self.golf = self._safe_instance("core.golf_ai_agent", "GolfAIAgent")
        self.medical = self._safe_instance("core.medical_supreme_engine", "MedicalSupremeEngine")
        self.fitness = self._safe_instance("core.fitness_performance_engine", "FitnessPerformanceEngine")

        self.geo = self._safe_instance("core.geopolitical_intelligence_engine", "GeopoliticalIntelligenceEngine")
        self.narrative = self._safe_instance("core.narrative_detection_engine", "NarrativeDetectionEngine")
        self.regime = self._safe_instance("core.macro_regime_engine", "MacroRegimeEngine")
        self.market_monitor = self._safe_instance("core.market_monitor", "MarketMonitor")
        self.data_fusion = self._safe_instance("core.data_fusion_engine", "DataFusionEngine")
        self.wealth = self._safe_instance("core.wealth_optimizer", "WealthOptimizer")
        self.family_office = self._safe_instance("core.family_office_engine", "FamilyOfficeEngine")

        self.email_engine = self._safe_instance("core.email_intelligence_engine", "EmailIntelligenceEngine")
        self.calendar_engine = self._safe_instance("core.calendar_intelligence_engine", "CalendarIntelligenceEngine")

        self.decision_router = {
            "computer_control": self._handle_computer_control,
            "linkedin_agent": self._handle_linkedin_agent,
            "image_generation": self._handle_image_generation,
            "video_analysis": self._handle_video_analysis,
            "golf_agent": self._handle_golf_agent,
            "golf_swing": self._handle_golf_agent,
            "golf_fitting": self._handle_golf_agent,
            "golf_biometrics": self._handle_golf_agent,
            "trader": self._handle_trader,
            "market_intelligence": self._handle_market_intelligence,
            "opportunity_hunter": self._handle_opportunity_hunter,
            "strategist": self._handle_strategist,
            "legal": self._handle_legal,
            "lawyer": self._handle_legal,
            "accounting": self._handle_accounting,
            "contador": self._handle_accounting,
            "medical": self._handle_medical,
            "fitness": self._handle_fitness,
            "personal_coach": self._handle_personal_coach,
            "email": self._handle_email,
            "calendar": self._handle_calendar,
            "wealth": self._handle_wealth,
            "family_office": self._handle_family_office,
            "conversation": self._handle_conversation,
        }

    # =========================================================
    # PUBLIC
    # =========================================================
    def execute(self, agent: str, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        started_at = datetime.utcnow().isoformat()
        normalized_agent = self._normalize_agent(agent)

        try:
            handler = self.decision_router.get(normalized_agent, self._handle_conversation)
            result = handler(task=task, payload=payload)

            response = {
                "status": "ok",
                "agent": normalized_agent,
                "task": task,
                "started_at": started_at,
                "finished_at": datetime.utcnow().isoformat(),
                "result": result,
            }

            self._remember(normalized_agent, task, response)
            self._audit("task_executor_success", response)

            return response

        except Exception as exc:
            error_payload = {
                "status": "error",
                "agent": normalized_agent,
                "task": task,
                "started_at": started_at,
                "finished_at": datetime.utcnow().isoformat(),
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }

            self._remember(normalized_agent, task, error_payload)
            self._audit("task_executor_error", error_payload)

            return error_payload

    # =========================================================
    # CORE HELPERS
    # =========================================================
    def _safe_instance(self, module_name: str, class_name: str):
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            return cls()
        except Exception:
            return None

    def _audit(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self.audit and hasattr(self.audit, "log_event"):
            try:
                self.audit.log_event(event_name, payload)
            except Exception:
                pass

    def _remember(self, agent: str, task: str, payload: Dict[str, Any]) -> None:
        if self.memory and hasattr(self.memory, "store"):
            try:
                summary = f"[{agent}] task={task} status={payload.get('status')}"
                self.memory.store("task_executor", summary)
            except Exception:
                pass

    def _normalize_agent(self, agent: str) -> str:
        value = (agent or "conversation").strip().lower()

        alias_map = {
            "abogado": "legal",
            "legal_compliance": "legal",
            "contador": "accounting",
            "finanzas": "accounting",
            "coach": "personal_coach",
            "coach_fitness": "fitness",
            "golf": "golf_agent",
            "swing": "golf_swing",
            "fitting": "golf_fitting",
            "biometrics": "golf_biometrics",
            "market": "market_intelligence",
            "opportunity": "opportunity_hunter",
            "trading": "trader",
            "computer": "computer_control",
            "linkedin": "linkedin_agent",
            "doctor": "medical",
            "medico": "medical",
            "correo": "email",
            "calendar": "calendar",
            "calendario": "calendar",
            "wealth_optimizer": "wealth",
        }

        return alias_map.get(value, value)

    def _conversation_reply(self, task: str, domain: str = "general") -> Dict[str, Any]:
        if self.conversation and hasattr(self.conversation, "reply"):
            return {
                "reply": self.conversation.reply(task, domain)
            }

        return {
            "reply": "No tengo disponible el motor conversacional en este momento."
        }

    def _first_present(self, *values):
        for v in values:
            if v is not None:
                return v
        return None

    # =========================================================
    # HANDLERS
    # =========================================================
    def _handle_conversation(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        domain = payload.get("domain", "general")
        return self._conversation_reply(task, domain)

    def _handle_computer_control(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.computer:
            return {"warning": "ComputerControlAgent not available", "fallback": "conversation"}

        action = (payload.get("action") or "").strip().lower()
        target = payload.get("target") or payload.get("app") or payload.get("url") or task

        if action == "open_website" and hasattr(self.computer, "open_website"):
            return self.computer.open_website(target)

        if action == "type_text" and hasattr(self.computer, "type_text"):
            text = payload.get("text") or task
            return self.computer.type_text(text)

        if action == "click" and hasattr(self.computer, "click"):
            return self.computer.click(int(payload.get("x", 0)), int(payload.get("y", 0)))

        if hasattr(self.computer, "open_application"):
            return self.computer.open_application(target)

        return {"warning": "ComputerControlAgent loaded but missing requested action"}

    def _handle_linkedin_agent(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.linkedin and hasattr(self.linkedin, "search_jobs"):
            keyword = payload.get("keyword") or task
            return self.linkedin.search_jobs(keyword)

        return {
            "warning": "LinkedinJobAgent not available",
            "fallback": self._conversation_reply(f"Busca oportunidades laborales relacionadas con: {task}", "career")
        }

    def _handle_image_generation(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = payload.get("prompt") or task

        if self.image and hasattr(self.image, "generate"):
            return {"image_url": self.image.generate(prompt), "prompt": prompt}

        return {
            "warning": "ImageGenerationEngine not available",
            "prompt": prompt
        }

    def _handle_video_analysis(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = payload.get("video_path") or payload.get("file_path") or task

        if self.video and hasattr(self.video, "analyze"):
            return self.video.analyze(path)

        return {
            "warning": "VideoAnalysisEngine not available",
            "path": path
        }

    def _handle_golf_agent(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Premium golf logic:
        - club recommendation
        - swing analysis from video
        - biometrics-aware recommendations
        - fitting logic
        - course-aware suggestions
        """
        distance = self._first_present(payload.get("distance"), payload.get("distance_yards"), 150)
        course = payload.get("course") or payload.get("field") or "unknown_course"
        wind = payload.get("wind") or "unknown"
        lie = payload.get("lie") or "unknown"
        video_path = payload.get("video_path")
        player_profile = payload.get("player_profile") or {}
        shot_shape = payload.get("shot_shape") or "neutral"

        output = {
            "course": course,
            "distance": distance,
            "wind": wind,
            "lie": lie,
            "shot_shape": shot_shape,
        }

        if self.golf:
            if video_path and hasattr(self.golf, "analyze_swing_video"):
                try:
                    output["swing_video_analysis"] = self.golf.analyze_swing_video(video_path, player_profile)
                except Exception as exc:
                    output["swing_video_analysis_error"] = str(exc)

            if hasattr(self.golf, "recommend_club"):
                try:
                    output["club_recommendation"] = self.golf.recommend_club(distance)
                except Exception as exc:
                    output["club_recommendation_error"] = str(exc)

            if hasattr(self.golf, "fitting_recommendation"):
                try:
                    output["fitting_recommendation"] = self.golf.fitting_recommendation(player_profile)
                except Exception:
                    pass

            if hasattr(self.golf, "biometrics_profile"):
                try:
                    output["biometrics_profile"] = self.golf.biometrics_profile(player_profile)
                except Exception:
                    pass

            if hasattr(self.golf, "detect_swing_faults") and video_path:
                try:
                    output["swing_faults"] = self.golf.detect_swing_faults(video_path)
                except Exception:
                    pass
        else:
            output["club_recommendation"] = self._golf_fallback_recommendation(distance)

        if "club_recommendation" not in output:
            output["club_recommendation"] = self._golf_fallback_recommendation(distance)

        if "swing_video_analysis" not in output and video_path:
            output["swing_video_analysis"] = {
                "status": "fallback_mode",
                "summary": "Se recibió video, pero no hay motor avanzado de swing cargado. Recomendación: activar pipeline de análisis frame-by-frame."
            }

        output["premium_notes"] = [
            "Ajustar por viento, lie, dispersión habitual y estado físico.",
            "No usar solo distancia bruta; considerar carry real y patrón de contacto.",
            "Si hay video, conviene validar secuencia, cara, path, tempo y transferencia de presión."
        ]

        return output

    def _golf_fallback_recommendation(self, distance: float) -> Dict[str, Any]:
        d = float(distance)
        if d < 95:
            club = "56° / SW"
        elif d < 110:
            club = "AW / Gap Wedge"
        elif d < 125:
            club = "PW"
        elif d < 140:
            club = "9 Iron"
        elif d < 155:
            club = "8 Iron"
        elif d < 170:
            club = "7 Iron"
        elif d < 185:
            club = "6 Iron"
        elif d < 200:
            club = "5 Iron"
        elif d < 220:
            club = "4 Iron / Hybrid"
        else:
            club = "3 Wood / Driver depending on lie and hole strategy"

        return {
            "recommended_club": club,
            "distance_basis": d,
            "mode": "fallback"
        }

    def _handle_trader(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_symbol = payload.get("symbol") or task

        if self.ticker_resolver and hasattr(self.ticker_resolver, "resolve"):
            symbol = self.ticker_resolver.resolve(raw_symbol)
        else:
            symbol = (raw_symbol or "").upper()

        if self.trader and hasattr(self.trader, "analyze"):
            result = self.trader.analyze(symbol)
            return result

        return {
            "warning": "TraderAlphaEngine not available",
            "symbol": symbol
        }

    def _handle_market_intelligence(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "task": task,
            "macro": None,
            "markets": None,
            "regime": None,
            "narratives": None,
        }

        try:
            if self.data_fusion and hasattr(self.data_fusion, "macro_summary"):
                result["macro"] = self.data_fusion.macro_summary()
        except Exception as exc:
            result["macro_error"] = str(exc)

        try:
            if self.data_fusion and hasattr(self.data_fusion, "market_snapshot"):
                result["markets"] = self.data_fusion.market_snapshot()
        except Exception as exc:
            result["markets_error"] = str(exc)

        try:
            if self.regime and hasattr(self.regime, "analyze"):
                result["regime"] = self.regime.analyze(task, payload.get("context", ""))
        except Exception as exc:
            result["regime_error"] = str(exc)

        try:
            if self.narrative and hasattr(self.narrative, "analyze"):
                result["narratives"] = self.narrative.analyze(task, payload.get("context", ""))
        except Exception as exc:
            result["narratives_error"] = str(exc)

        if not any([result.get("macro"), result.get("markets"), result.get("regime"), result.get("narratives")]):
            result["fallback"] = self._conversation_reply(task, "macro")

        return result

    def _handle_opportunity_hunter(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "task": task,
            "geopolitical": None,
            "narrative": None,
            "regime": None,
            "market_scan": None,
            "opportunities": [],
        }

        try:
            if self.geo and hasattr(self.geo, "analyze"):
                result["geopolitical"] = self.geo.analyze(task, payload.get("context", ""))
        except Exception as exc:
            result["geopolitical_error"] = str(exc)

        try:
            if self.narrative and hasattr(self.narrative, "analyze"):
                result["narrative"] = self.narrative.analyze(task, payload.get("context", ""))
        except Exception as exc:
            result["narrative_error"] = str(exc)

        try:
            if self.regime and hasattr(self.regime, "analyze"):
                result["regime"] = self.regime.analyze(task, payload.get("context", ""))
        except Exception as exc:
            result["regime_error"] = str(exc)

        try:
            if self.market_monitor and hasattr(self.market_monitor, "scan"):
                result["market_scan"] = self.market_monitor.scan()
        except Exception as exc:
            result["market_scan_error"] = str(exc)

        result["opportunities"].append("Buscar activos baratos con catalizador macro.")
        result["opportunities"].append("Cruzar narrativa + régimen + momentum + valuación.")
        result["opportunities"].append("Separar oportunidades tácticas de estructurales.")

        return result

    def _handle_strategist(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._conversation_reply(task, payload.get("domain", "strategy"))

    def _handle_legal(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legal premium wrapper.
        Uses conversation fallback if dedicated legal engine is not present.
        """
        jurisdiction = payload.get("jurisdiction", "colombia")
        domain = payload.get("domain", "legal")

        return {
            "jurisdiction": jurisdiction,
            "guidance": self._conversation_reply(
                f"Analiza legalmente esto en {jurisdiction}: {task}. Sé preciso, conservador y práctico.",
                domain
            )
        }

    def _handle_accounting(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("financials") or {}
        if data:
            revenue = float(data.get("revenue", 0))
            cogs = float(data.get("cogs", 0))
            opex = float(data.get("opex", 0))
            debt = float(data.get("debt", 0))
            cash = float(data.get("cash", 0))

            gross_profit = revenue - cogs
            ebitda_proxy = gross_profit - opex

            return {
                "gross_profit": gross_profit,
                "ebitda_proxy": ebitda_proxy,
                "net_debt": debt - cash,
                "summary": "Accounting wrapper generated profitability and leverage view."
            }

        return self._conversation_reply(
            f"Actúa como contador premium y analiza esto de forma práctica: {task}",
            "accounting"
        )

    def _handle_medical(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.medical:
            if payload.get("symptoms") and hasattr(self.medical, "symptom_triage"):
                return self.medical.symptom_triage(
                    symptoms=payload.get("symptoms"),
                    age=payload.get("age"),
                    context=payload.get("context", "")
                )

            if payload.get("lab_text") and hasattr(self.medical, "interpret_labs"):
                return self.medical.interpret_labs(payload.get("lab_text"))

            if hasattr(self.medical, "treatment_support"):
                return self.medical.treatment_support(payload.get("context", task))

        return self._conversation_reply(
            f"Actúa como médico premium conservador y útil. Analiza esto: {task}",
            "medical"
        )

    def _handle_fitness(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.fitness:
            if payload.get("mode") == "microcycle" and hasattr(self.fitness, "build_microcycle"):
                return self.fitness.build_microcycle(
                    goal=payload.get("goal", "strength_golf"),
                    days=int(payload.get("days", 7)),
                    equipment=payload.get("equipment"),
                    golf_swings_per_day=int(payload.get("golf_swings_per_day", 50)),
                )

            if payload.get("mode") == "nutrition" and hasattr(self.fitness, "nutrition_strategy"):
                return self.fitness.nutrition_strategy(
                    weight_kg=float(payload.get("weight_kg", 53.0)),
                    goal=payload.get("goal", "lean_mass"),
                )

            if hasattr(self.fitness, "recovery_plan"):
                return self.fitness.recovery_plan(payload.get("context", task))

        return self._conversation_reply(
            f"Actúa como coach fitness premium y responde práctico: {task}",
            "fitness"
        )

    def _handle_personal_coach(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._conversation_reply(
            f"Actúa como coach personal premium, estratégico, claro y accionable: {task}",
            payload.get("domain", "personal_coach")
        )

    def _handle_email(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.email_engine and hasattr(self.email_engine, "draft_reply"):
            sender = payload.get("sender", "unknown@example.com")
            subject = payload.get("subject", "Draft")
            body = payload.get("body", task)
            tone = payload.get("tone", "professional")
            return self.email_engine.draft_reply(sender, subject, body, tone)

        return self._conversation_reply(
            f"Redacta un correo premium corto y claro sobre esto: {task}",
            "email"
        )

    def _handle_calendar(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.calendar_engine and hasattr(self.calendar_engine, "plan"):
            return self.calendar_engine.plan(
                objective=payload.get("objective", task),
                duration_minutes=int(payload.get("duration_minutes", 30)),
                participants=payload.get("participants", []),
            )

        return self._conversation_reply(
            f"Organiza una reunión o agenda de forma clara y práctica: {task}",
            "calendar"
        )

    def _handle_wealth(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        capital = payload.get("capital")
        if capital is not None and self.wealth and hasattr(self.wealth, "optimize"):
            return self.wealth.optimize(float(capital))

        return self._conversation_reply(
            f"Actúa como wealth optimizer premium y analiza esto: {task}",
            "wealth"
        )

    def _handle_family_office(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.family_office and hasattr(self.family_office, "analyze_wealth"):
            return self.family_office.analyze_wealth(payload)

        return self._conversation_reply(
            f"Actúa como family office advisor premium y analiza esto: {task}",
            "family_office"
        )
