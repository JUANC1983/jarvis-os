import os
from openai import OpenAI
from core.real_agent_council import RealAgentCouncil
from core.super_memory_system import SuperMemorySystem


class ConversationEngine:

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.council = RealAgentCouncil()
        self.memory = SuperMemorySystem()

    def _needs_deep_reasoning(self, message: str) -> bool:
        m = message.lower()
        triggers = [
            "analiza",
            "analysis",
            "deep",
            "estrategia",
            "estrategico",
            "portfolio",
            "portafolio",
            "macro",
            "geopolitica",
            "trade"
        ]
        return any(t in m for t in triggers)

    def reply(self, message: str, domain: str = "general") -> str:

        try:
            # =========================
            # MEMORY (LIGERO)
            # =========================
            memories = self.memory.search(message) or []
            memory_context = "\n".join(memories[:3]) if memories else ""

            # =========================
            # COUNCIL (SOLO SI NECESARIO)
            # =========================
            council_analysis = ""

            if self._needs_deep_reasoning(message):
                try:
                    council = self.council.deliberate(
                        topic=message,
                        domain=domain,
                        owner_name="Juan Camilo"
                    )
                    council_analysis = council.get("consensus", "")
                except Exception:
                    council_analysis = ""

            # =========================
            # PROMPT OPTIMIZADO
            # =========================
            prompt = f"""
You are JARVIS.

Speak like a real human assistant.

Rules:
- Speak naturally
- Default Spanish
- Same language as user
- Be concise (1-3 sentences)
- No AI explanations

User: {message}
"""

            # =========================
            # OPENAI CALL
            # =========================
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=120
            )

            reply = (resp.choices[0].message.content or "").strip()

            # =========================
            # FALLBACK CRÍTICO
            # =========================
            if not reply:
                reply = "Estoy aquí. ¿Qué necesitas?"

            # =========================
            # MEMORY STORE (NO BLOQUEANTE)
            # =========================
            try:
                self.memory.store("chat_memory", message)
                self.memory.store("chat_memory", reply)
            except Exception:
                pass

            return reply

        except Exception as e:
            # =========================
            # FALLBACK GLOBAL
            # =========================
            return "Tuve un problema respondiendo. Intenta de nuevo."