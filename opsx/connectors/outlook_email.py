"""
Microsoft Graph API email operations.
All Graph calls route through safe_graph_call() for automatic token refresh on 401.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from opsx.connectors.outlook_auth import (
    TokenExpiredError,
    safe_graph_call,
)

log = logging.getLogger("jarvis.outlook_email")

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_MESSAGE_SELECT = (
    "id,subject,bodyPreview,body,from,toRecipients,ccRecipients,"
    "receivedDateTime,conversationId,importance,isRead,hasAttachments,categories"
)


# ── Read operations ───────────────────────────────────────────────────────────

async def fetch_email(message_id: str, user_id: str = "owner") -> Optional[Dict]:
    """Fetch a single message by ID. Returns None on network error; raises TokenExpiredError on auth failure."""
    try:
        resp = await safe_graph_call(
            "get",
            f"{_GRAPH_BASE}/me/messages/{message_id}",
            user_id,
            params={"$select": _MESSAGE_SELECT},
        )
        if resp.status_code == 200:
            return _parse_message(resp.json())
        log.error("fetch_email %s HTTP %d: %s", message_id, resp.status_code, resp.text[:200])
        return None
    except TokenExpiredError:
        raise
    except Exception as exc:
        log.error("fetch_email error: %s", exc)
        return None


async def list_inbox(
    limit: int = 20,
    user_id: str = "owner",
    unread_only: bool = False,
) -> List[Dict]:
    """Return recent inbox messages, newest first. Raises TokenExpiredError on auth failure."""
    params: Dict = {
        "$top":     limit,
        "$orderby": "receivedDateTime desc",
        "$select":  "id,subject,bodyPreview,from,receivedDateTime,isRead,importance,conversationId",
    }
    if unread_only:
        params["$filter"] = "isRead eq false"
    try:
        resp = await safe_graph_call(
            "get",
            f"{_GRAPH_BASE}/me/mailFolders/Inbox/messages",
            user_id,
            params=params,
        )
        if resp.status_code == 200:
            return [_parse_message(m) for m in resp.json().get("value", [])]
        log.error("list_inbox HTTP %d: %s", resp.status_code, resp.text[:200])
        return []
    except TokenExpiredError:
        raise
    except Exception as exc:
        log.error("list_inbox error: %s", exc)
        return []


async def count_unread(user_id: str = "owner") -> int:
    """Return unread message count. Raises TokenExpiredError on auth failure; returns 0 on network error."""
    try:
        resp = await safe_graph_call(
            "get",
            f"{_GRAPH_BASE}/me/mailFolders/Inbox",
            user_id,
            params={"$select": "unreadItemCount"},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json().get("unreadItemCount", 0)
        log.error("count_unread HTTP %d: %s", resp.status_code, resp.text[:200])
        return 0
    except TokenExpiredError:
        raise
    except Exception as exc:
        log.error("count_unread error: %s", exc)
        return 0


# ── Write operations ──────────────────────────────────────────────────────────

async def send_reply(
    message_id: str,
    reply_body: str,
    user_id: str = "owner",
) -> bool:
    """Send a reply. Returns True on 202. Raises TokenExpiredError on auth failure."""
    payload = {
        "message": {
            "body": {"contentType": "Text", "content": reply_body}
        },
        "comment": reply_body,
    }
    try:
        resp = await safe_graph_call(
            "post",
            f"{_GRAPH_BASE}/me/messages/{message_id}/reply",
            user_id,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=25.0,
        )
        if resp.status_code == 202:
            log.info("Reply sent for message=%s user=%s", message_id, user_id)
            return True
        log.error("send_reply HTTP %d: %s", resp.status_code, resp.text[:200])
        return False
    except TokenExpiredError:
        raise
    except Exception as exc:
        log.error("send_reply error: %s", exc)
        return False


async def delete_email(message_id: str, user_id: str = "owner") -> bool:
    """Move message to Deleted Items. Raises TokenExpiredError on auth failure."""
    try:
        resp = await safe_graph_call(
            "delete",
            f"{_GRAPH_BASE}/me/messages/{message_id}",
            user_id,
            timeout=15.0,
        )
        return resp.status_code == 204
    except TokenExpiredError:
        raise
    except Exception as exc:
        log.error("delete_email error: %s", exc)
        return False


async def mark_as_read(message_id: str, user_id: str = "owner") -> bool:
    """Mark a message as read. Raises TokenExpiredError on auth failure."""
    try:
        resp = await safe_graph_call(
            "patch",
            f"{_GRAPH_BASE}/me/messages/{message_id}",
            user_id,
            headers={"Content-Type": "application/json"},
            json={"isRead": True},
            timeout=15.0,
        )
        return resp.status_code == 200
    except TokenExpiredError:
        raise
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
        "body_text":       body_text[:8000],
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
