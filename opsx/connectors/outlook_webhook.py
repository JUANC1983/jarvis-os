"""
Microsoft Graph Webhook subscription manager.
Handles creation, validation, renewal, and deletion of inbox subscriptions.
Auto-renewal runs as a background asyncio task.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx

from opsx.connectors.outlook_auth import get_valid_token

log = logging.getLogger("jarvis.outlook_webhook")

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_NOTIFICATION_URL = os.getenv(
    "WEBHOOK_NOTIFICATION_URL",
    "https://jarvis-os-production.up.railway.app/webhook/outlook",
)

# clientState secret — used to validate incoming notifications
_CLIENT_STATE = os.getenv("WEBHOOK_CLIENT_STATE", "jarvis-outlook-secret-v1")

# Microsoft limits mail subscription to max 4230 minutes (~3 days)
_SUBSCRIPTION_TTL_MINUTES = 4000
# Renew when fewer than this many minutes remain
_RENEW_THRESHOLD_MINUTES  = 90


# ── Subscription store ────────────────────────────────────────────────────────

class SubscriptionStore:
    """In-memory subscription store. Swap _data for DB to persist across restarts."""

    def __init__(self) -> None:
        self._data: Dict[str, Dict] = {}   # user_id → subscription object

    def save(self, user_id: str, sub: Dict) -> None:
        self._data[user_id] = sub
        log.info(
            "Subscription saved user=%s id=%s expires=%s",
            user_id, sub.get("id"), sub.get("expirationDateTime"),
        )

    def get(self, user_id: str) -> Optional[Dict]:
        return self._data.get(user_id)

    def remove(self, user_id: str) -> None:
        self._data.pop(user_id, None)

    def all_users(self) -> List[str]:
        return list(self._data.keys())

    def is_near_expiry(self, user_id: str) -> bool:
        sub = self._data.get(user_id)
        if not sub or not sub.get("expirationDateTime"):
            return True
        try:
            raw = sub["expirationDateTime"]
            # Graph returns Z-suffix ISO timestamps
            exp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) >= exp - timedelta(minutes=_RENEW_THRESHOLD_MINUTES)
        except Exception:
            return True

    def summary(self) -> List[Dict]:
        return [
            {
                "user_id":   uid,
                "sub_id":    s.get("id"),
                "expires":   s.get("expirationDateTime"),
                "near_expiry": self.is_near_expiry(uid),
            }
            for uid, s in self._data.items()
        ]


subscription_store = SubscriptionStore()


# ── Subscription lifecycle ────────────────────────────────────────────────────

def _expiry_str() -> str:
    dt = datetime.now(timezone.utc) + timedelta(minutes=_SUBSCRIPTION_TTL_MINUTES)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


async def create_subscription(user_id: str = "owner") -> Optional[Dict]:
    """
    Register a new Microsoft Graph webhook subscription for the user's inbox.
    Stores the subscription for future renewal.
    """
    token = await get_valid_token(user_id)
    if not token:
        log.error("Cannot create subscription — no valid token for user=%s", user_id)
        return None

    payload = {
        "changeType":         "created",
        "notificationUrl":    _NOTIFICATION_URL,
        "resource":           "/me/mailFolders('Inbox')/messages",
        "expirationDateTime": _expiry_str(),
        "clientState":        _CLIENT_STATE,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{_GRAPH_BASE}/subscriptions",
                headers={
                    "Authorization":  f"Bearer {token}",
                    "Content-Type":   "application/json",
                },
                json=payload,
            )
            if resp.status_code == 201:
                sub = resp.json()
                subscription_store.save(user_id, sub)
                log.info("Subscription CREATED id=%s user=%s", sub.get("id"), user_id)
                return sub
            else:
                log.error(
                    "Subscription creation failed %d for user=%s: %s",
                    resp.status_code, user_id, resp.text[:400],
                )
                return None
    except Exception as exc:
        log.error("create_subscription error for user=%s: %s", user_id, exc)
        return None


async def renew_subscription(user_id: str = "owner") -> bool:
    """
    Extend the expiration of an existing subscription.
    If not found in Graph (404), recreates it transparently.
    """
    sub = subscription_store.get(user_id)
    if not sub:
        log.warning("No stored subscription for user=%s — creating fresh", user_id)
        return (await create_subscription(user_id)) is not None

    token = await get_valid_token(user_id)
    if not token:
        log.error("Cannot renew — no valid token for user=%s", user_id)
        return False

    sub_id = sub.get("id")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.patch(
                f"{_GRAPH_BASE}/subscriptions/{sub_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type":  "application/json",
                },
                json={"expirationDateTime": _expiry_str()},
            )
            if resp.status_code == 200:
                subscription_store.save(user_id, resp.json())
                log.info("Subscription RENEWED id=%s user=%s", sub_id, user_id)
                return True
            elif resp.status_code == 404:
                log.warning("Subscription %s not found — recreating for user=%s", sub_id, user_id)
                subscription_store.remove(user_id)
                return (await create_subscription(user_id)) is not None
            else:
                log.error(
                    "Subscription renewal failed %d for sub=%s: %s",
                    resp.status_code, sub_id, resp.text[:200],
                )
                return False
    except Exception as exc:
        log.error("renew_subscription error for user=%s: %s", user_id, exc)
        return False


async def delete_subscription(user_id: str = "owner") -> bool:
    """Delete the subscription from Graph and local store."""
    sub = subscription_store.get(user_id)
    if not sub:
        return True
    token = await get_valid_token(user_id)
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{_GRAPH_BASE}/subscriptions/{sub['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            subscription_store.remove(user_id)
            return resp.status_code in (204, 404)
    except Exception as exc:
        log.error("delete_subscription error: %s", exc)
        return False


# ── Notification validation ───────────────────────────────────────────────────

def validate_client_state(received_state: str) -> bool:
    """
    Validate the clientState field from incoming webhook notifications.
    This is the primary security check that the notification is from Microsoft.
    """
    return received_state == _CLIENT_STATE


# ── Auto-renewal background loop ──────────────────────────────────────────────

_renewal_task: Optional[asyncio.Task] = None


async def _renewal_loop() -> None:
    """
    Checks all subscriptions every 60 minutes.
    Renews any that are within _RENEW_THRESHOLD_MINUTES of expiry.
    """
    log.info("Subscription auto-renewal loop started")
    while True:
        try:
            await asyncio.sleep(3600)  # Check every hour
            users = subscription_store.all_users()
            log.debug("Renewal check: %d subscriptions", len(users))
            for user_id in users:
                if subscription_store.is_near_expiry(user_id):
                    log.info("Renewing near-expiry subscription for user=%s", user_id)
                    await renew_subscription(user_id)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("Renewal loop error: %s", exc)


def start_renewal_loop() -> None:
    global _renewal_task
    _renewal_task = asyncio.create_task(_renewal_loop())


async def stop_renewal_loop() -> None:
    global _renewal_task
    if _renewal_task:
        _renewal_task.cancel()
        try:
            await _renewal_task
        except asyncio.CancelledError:
            pass
