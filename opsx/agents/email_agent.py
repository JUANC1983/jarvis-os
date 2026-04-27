"""
Two-stage AI email processing pipeline.

Stage 1 — Analysis:
  language, intent, type, priority, summary, key_points, draft_reply, suggested_actions

Stage 2 — Humanizer + QA:
  Takes the draft reply and produces a natural, tone-matched final_reply with confidence score.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, Literal, Optional

log = logging.getLogger("jarvis.email_agent")

_MODEL = os.getenv("EMAIL_AI_MODEL", "gpt-4o-mini")

try:
    import openai as _openai
    _async_client = _openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    _AI_AVAILABLE = True
except Exception:
    _async_client = None  # type: ignore
    _AI_AVAILABLE = False


# ── Stage 1: Analysis ─────────────────────────────────────────────────────────

_S1_SYSTEM = """\
You are JARVIS — an elite executive email intelligence system.

Analyze the email and return ONLY a JSON object with these exact fields:
{
  "language_detected": "Spanish" | "English" | "Mixed",
  "intent": "urgent" | "normal" | "informational" | "spam" | "action_required",
  "email_type": "client" | "internal" | "system" | "unknown",
  "priority": "high" | "medium" | "low",
  "requires_action": true | false,
  "summary": "<concise executive summary, max 2 sentences, same language as email>",
  "key_points": ["<point1>", "<point2>"],
  "draft_reply": "<initial reply draft, same language as email, empty string if spam>",
  "suggested_actions": {
    "create_task": true | false,
    "create_calendar_event": true | false,
    "follow_up_reminder": true | false
  },
  "sentiment": "positive" | "neutral" | "negative" | "urgent"
}

STRICT RULES:
- summary and draft_reply MUST be in the same language as the email
- high priority = requires immediate action, client/executive, has deadline
- spam = no reply, no action; set draft_reply to ""
- Never fabricate information not present in the email
"""

_S1_USER = """\
EMAIL:
From: {sender_name} <{sender_email}>
Subject: {subject}

{body_text}
"""


# ── Stage 2: Humanizer ────────────────────────────────────────────────────────

_S2_SYSTEM = """\
You are JARVIS HumanizeAI — you transform AI email drafts into natural, professional responses.

Return ONLY a JSON object:
{
  "final_reply": "<polished, human-sounding reply>",
  "tone_used": "professional" | "concise" | "action-oriented" | "friendly" | "formal",
  "confidence_score": <0.0 to 1.0>,
  "changes_made": "<one sentence describing improvements>"
}

TRANSFORMATION RULES:
1. REMOVE all robotic phrases: "Certainly!", "Of course!", "I hope this email finds you well",
   "Please do not hesitate", "As per our previous conversation", "Best regards, JARVIS"
2. ADAPT tone:
   - client → polite, helpful, professional (not stiff)
   - internal → direct and concise, no fluff
   - urgent → short, action-first
3. MATCH language EXACTLY — if draft is Spanish reply in Spanish, English → English
4. Keep response SHORT and ACTIONABLE (max 5 sentences unless content requires more)
5. Sound like a confident senior professional, not an AI assistant
6. Never add facts not in the draft
7. confidence_score: 0.9+ = clear and appropriate; 0.7–0.9 = minor uncertainty; <0.7 = human review strongly recommended
"""

_S2_USER = """\
Email context:
- Type: {email_type}
- Intent: {intent}
- Language: {language_detected}
- Sender: {sender_name}

DRAFT TO HUMANIZE:
{draft_reply}
"""


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def process_email(email: Dict) -> Dict:
    """
    Full two-stage AI processing of an email.
    Returns a structured result dict ready for the email store and dashboard.
    """
    t0 = time.monotonic()
    log.info(
        "Processing email: subject=%r sender=%s",
        email.get("subject"), email.get("sender_email"),
    )

    stage1 = await _run_stage1(email) if _AI_AVAILABLE else _fallback_stage1(email)
    stage2: Optional[Dict] = None

    if _AI_AVAILABLE and stage1.get("intent") != "spam" and stage1.get("draft_reply"):
        stage2 = await _run_stage2(email, stage1)

    elapsed = time.monotonic() - t0
    log.info(
        "Email processed in %.2fs — priority=%s intent=%s stage2=%s",
        elapsed, stage1.get("priority"), stage1.get("intent"), stage2 is not None,
    )
    return _build_result(email, stage1, stage2, elapsed)


async def _run_stage1(email: Dict) -> Dict:
    body = (email.get("body_text") or email.get("body_preview") or "")[:4000]
    user_msg = _S1_USER.format(
        sender_name  = email.get("sender_name", "Unknown"),
        sender_email = email.get("sender_email", ""),
        subject      = email.get("subject", ""),
        body_text    = body,
    )
    try:
        resp = await _async_client.chat.completions.create(  # type: ignore[union-attr]
            model           = _MODEL,
            messages        = [
                {"role": "system", "content": _S1_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
            response_format = {"type": "json_object"},
            temperature     = 0.3,
            max_tokens      = 900,
        )
        return json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError as exc:
        log.error("Stage1 JSON parse error: %s", exc)
        return _fallback_stage1(email)
    except Exception as exc:
        log.error("Stage1 AI error: %s", exc)
        return _fallback_stage1(email)


async def _run_stage2(email: Dict, stage1: Dict) -> Optional[Dict]:
    user_msg = _S2_USER.format(
        email_type        = stage1.get("email_type", "unknown"),
        intent            = stage1.get("intent", "normal"),
        language_detected = stage1.get("language_detected", "English"),
        sender_name       = email.get("sender_name", ""),
        draft_reply       = stage1.get("draft_reply", ""),
    )
    try:
        resp = await _async_client.chat.completions.create(  # type: ignore[union-attr]
            model           = _MODEL,
            messages        = [
                {"role": "system", "content": _S2_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
            response_format = {"type": "json_object"},
            temperature     = 0.4,
            max_tokens      = 700,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as exc:
        log.error("Stage2 AI error: %s", exc)
        return None


def _build_result(
    email: Dict,
    s1: Dict,
    s2: Optional[Dict],
    elapsed: float,
) -> Dict:
    return {
        # Email metadata
        "message_id":      email.get("id"),
        "conversation_id": email.get("conversation_id"),
        "subject":         email.get("subject"),
        "sender_name":     email.get("sender_name"),
        "sender_email":    email.get("sender_email"),
        "received_at":     email.get("received_at"),
        "has_attachments": email.get("has_attachments", False),
        "is_read":         email.get("is_read", False),
        # Stage 1
        "language":          s1.get("language_detected", "Unknown"),
        "intent":            s1.get("intent", "normal"),
        "email_type":        s1.get("email_type", "unknown"),
        "priority":          s1.get("priority", "medium"),
        "requires_action":   s1.get("requires_action", False),
        "summary":           s1.get("summary", ""),
        "key_points":        s1.get("key_points", []),
        "sentiment":         s1.get("sentiment", "neutral"),
        "suggested_actions": s1.get("suggested_actions", {
            "create_task": False,
            "create_calendar_event": False,
            "follow_up_reminder": False,
        }),
        # Stage 2
        "draft_reply":     s1.get("draft_reply", ""),
        "final_reply":     (s2 or {}).get("final_reply") or s1.get("draft_reply", ""),
        "tone_used":       (s2 or {}).get("tone_used", "professional"),
        "confidence_score":(s2 or {}).get("confidence_score", 0.7),
        "stage2_applied":  s2 is not None,
        # Processing meta
        "ai_processing_ms": int(elapsed * 1000),
        "status":           "pending_approval",
    }


def _fallback_stage1(email: Dict) -> Dict:
    """Safe fallback when AI call fails — never crash the pipeline."""
    return {
        "language_detected": "Unknown",
        "intent":            "normal",
        "email_type":        "unknown",
        "priority":          "medium",
        "requires_action":   True,
        "summary":           (email.get("body_preview") or "")[:200] or "No summary available.",
        "key_points":        [],
        "draft_reply":       "",
        "suggested_actions": {
            "create_task":           False,
            "create_calendar_event": False,
            "follow_up_reminder":    False,
        },
        "sentiment": "neutral",
    }
