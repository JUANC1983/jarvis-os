"""
Microsoft Graph API email operations.
Fetch, parse, send, delete, and mark-read via /me/messages.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

import httpx

from opsx.connectors.outlook_auth import get_valid_token

log = logging.getLogger("jarvis.outlook_email")

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_MESSAGE_SELECT = (
    "id,subject,bodyPreview,body,from,toRecipients,ccRecipients,"
    "receivedDateTime,conversationId,importance,isRead,hasAttachments,categories"
)


# ── Read operations ───────────────────────────────────────────────────────────

async def fetch_email(message_id: str, user_id: str = "owner") -> Optional[Dict]:
    """Fetch a single message by ID and return normalised dict."""
    token = await get_valid_token(user_id)
    if not token:
        log.error("fetch_email: no valid token for user=%s", user_id)
        return None
    print(f"[GRAPH] fetch_email using token: {token[:20]}...")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_GRAPH_BASE}/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"$select": _MESSAGE_SELECT},
            )
        print(f"[GRAPH] fetch_email HTTP {resp.status_code}")
        if resp.status_code == 200:
            return _parse_message(resp.json())
        print(f"[GRAPH RESPONSE] {resp.text[:600]}")
        if resp.status_code == 401:
            log.error("fetch_email 401 — token rejected by Graph. Body: %s", resp.text[:400])
        else:
            log.error("fetch_email %s HTTP %d: %s", message_id, resp.status_code, resp.text[:200])
        return None
    except Exception as exc:
        log.error("fetch_email error: %s", exc)
        return None


async def list_inbox(
    limit: int = 20,
    user_id: str = "owner",
    unread_only: bool = False,
) -> List[Dict]:
    """Return recent inbox messages, newest first."""
    token = await get_valid_token(user_id)
    if not token:
        raise ValueError("Invalid or expired token. Re-auth required.")
    print(f"[GRAPH] list_inbox using token: {token[:20]}...")
    params: Dict = {
        "$top":     limit,
        "$orderby": "receivedDateTime desc",
        "$select":  "id,subject,bodyPreview,from,receivedDateTime,isRead,importance,conversationId",
    }
    if unread_only:
        params["$filter"] = "isRead eq false"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_GRAPH_BASE}/me/mailFolders/Inbox/messages",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
        print(f"[GRAPH] list_inbox HTTP {resp.status_code}")
        if resp.status_code == 200:
            return [_parse_message(m) for m in resp.json().get("value", [])]
        print(f"[GRAPH RESPONSE] {resp.text[:600]}")
        if resp.status_code == 401:
            log.error("list_inbox 401 — token rejected by Graph. Body: %s", resp.text[:400])
            raise ValueError("Invalid or expired token. Re-auth required.")
        log.error("list_inbox HTTP %d: %s", resp.status_code, resp.text[:200])
        return []
    except ValueError:
        raise
    except Exception as exc:
        log.error("list_inbox error: %s", exc)
        return []


async def count_unread(user_id: str = "owner") -> int:
    """Return unread message count for the inbox."""
    token = await get_valid_token(user_id)
    if not token:
        return 0
    print(f"[GRAPH] count_unread using token: {token[:20]}...")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{_GRAPH_BASE}/me/mailFolders/Inbox",
                headers={"Authorization": f"Bearer {token}"},
                params={"$select": "unreadItemCount"},
            )
        print(f"[GRAPH] count_unread HTTP {resp.status_code}")
        if resp.status_code == 200:
            return resp.json().get("unreadItemCount", 0)
        if resp.status_code == 401:
            print(f"[GRAPH RESPONSE] count_unread 401: {resp.text[:400]}")
        return 0
    except Exception:
        return 0


# ── Write operations ──────────────────────────────────────────────────────────

async def send_reply(
    message_id: str,
    reply_body: str,
    user_id: str = "owner",
) -> bool:
    """
    Send a reply to an email thread.
    reply_body is sent as plain text.
    """
    token = await get_valid_token(user_id)
    if not token:
        log.error("send_reply: no valid token for user=%s", user_id)
        return False
    payload = {
        "message": {
            "body": {"contentType": "Text", "content": reply_body}
        },
        "comment": reply_body,
    }
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                f"{_GRAPH_BASE}/me/messages/{message_id}/reply",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type":  "application/json",
                },
                json=payload,
            )
            if resp.status_code == 202:
                log.info("Reply sent for message=%s user=%s", message_id, user_id)
                return True
            log.error("send_reply HTTP %d: %s", resp.status_code, resp.text[:200])
            return False
    except Exception as exc:
        log.error("send_reply error: %s", exc)
        return False


async def delete_email(message_id: str, user_id: str = "owner") -> bool:
    """Move message to Deleted Items (soft delete via Graph DELETE)."""
    token = await get_valid_token(user_id)
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{_GRAPH_BASE}/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code == 204
    except Exception as exc:
        log.error("delete_email error: %s", exc)
        return False


async def mark_as_read(message_id: str, user_id: str = "owner") -> bool:
    """Mark a message as read."""
    token = await get_valid_token(user_id)
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                f"{_GRAPH_BASE}/me/messages/{message_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type":  "application/json",
                },
                json={"isRead": True},
            )
            return resp.status_code == 200
    except Exception as exc:
        log.error("mark_as_read error: %s", exc)
        return False


# ── Message parser ────────────────────────────────────────────────────────────

def _parse_message(raw: Dict) -> Dict:
    """Normalise a Graph message object into a clean, flat dict."""
    body_html = raw.get("body", {}).get("content", "")
    body_text = _strip_html(body_html) if body_html else raw.get("bodyPreview", "")

    sender    = raw.get("from", {}).get("emailAddress", {})
    recipients = [
        r["emailAddress"]["address"]
        for r in raw.get("toRecipients", [])
        if r.get("emailAddress", {}).get("address")
    ]
    return {
        "id":              raw.get("id"),
        "conversation_id": raw.get("conversationId"),
        "subject":         raw.get("subject") or "(No subject)",
        "sender_name":     sender.get("name", ""),
        "sender_email":    sender.get("address", ""),
        "recipients":      recipients,
        "body_text":       body_text[:8000],   # cap for AI token safety
        "body_preview":    raw.get("bodyPreview", "")[:400],
        "received_at":     raw.get("receivedDateTime"),
        "importance":      raw.get("importance", "normal"),
        "is_read":         raw.get("isRead", False),
        "has_attachments": raw.get("hasAttachments", False),
        "categories":      raw.get("categories", []),
    }


def _strip_html(html: str) -> str:
    """Minimal HTML-to-text conversion for email bodies."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
