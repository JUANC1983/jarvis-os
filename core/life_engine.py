"""Life Engine — Reminders, Shopping, Calls, Payments per user.

All data persisted as JSON under data/life/{user_id}/
Thread-safe; all public methods return dicts ready for JSON serialisation.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── helpers ──────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().isoformat()

def _gen_id() -> str:
    return hashlib.sha256(datetime.utcnow().isoformat().encode()).hexdigest()[:10]

def _parse_due(text: str) -> str:
    """Convert common Spanish/English date phrases to ISO datetime string."""
    now = datetime.utcnow()
    t = text.lower().strip()

    # Explicit time "a las HH:MM"
    time_match = re.search(r"a\s+las?\s+(\d{1,2})(?::(\d{2}))?", t)
    hour   = int(time_match.group(1)) if time_match else 9
    minute = int(time_match.group(2)) if (time_match and time_match.group(2)) else 0

    # Day resolution
    if "mañana" in t or "manana" in t:
        base = now + timedelta(days=1)
    elif "hoy" in t or "today" in t:
        base = now
        if not time_match:
            hour = 18  # hoy without time → this evening
    elif "lunes" in t or "monday" in t:
        base = _next_weekday(now, 0)
    elif "martes" in t or "tuesday" in t:
        base = _next_weekday(now, 1)
    elif "miércoles" in t or "miercoles" in t or "wednesday" in t:
        base = _next_weekday(now, 2)
    elif "jueves" in t or "thursday" in t:
        base = _next_weekday(now, 3)
    elif "viernes" in t or "friday" in t:
        base = _next_weekday(now, 4)
    elif "sábado" in t or "sabado" in t or "saturday" in t:
        base = _next_weekday(now, 5)
    elif "domingo" in t or "sunday" in t:
        base = _next_weekday(now, 6)
    elif "esta semana" in t or "this week" in t:
        base = _next_weekday(now, 4)  # Friday
    elif "próxima semana" in t or "proxima semana" in t or "next week" in t:
        base = now + timedelta(weeks=1)
    elif m := re.search(r"en\s+(\d+)\s+d[ií]as?", t):
        base = now + timedelta(days=int(m.group(1)))
    else:
        base = now + timedelta(days=1)  # default: tomorrow

    return base.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()


def _next_weekday(dt: datetime, weekday: int) -> datetime:
    """Return the next occurrence of weekday (0=Mon … 6=Sun) after dt."""
    days = (weekday - dt.weekday() + 7) % 7
    if days == 0:
        days = 7
    return dt + timedelta(days=days)


# ── NLP intent + title extraction ────────────────────────────────────────

_PAYMENT_KWS  = ["pagar", "pay", "factura", "bill", "luz", "agua", "arriendo", "rent",
                 "tarjeta", "card", "cuota", "recibo", "transferir", "transfer"]
_CALL_KWS     = ["llamar", "call", "telefonear", "hablar con", "contactar"]
_SHOPPING_KWS = ["comprar", "buy", "mercar", "supermercado", "grocery", "traer",
                 "necesito", "falta", "conseguir"]

_STOP_WORDS = {
    "tengo", "que", "debo", "hay", "necesito", "mañana", "manana", "hoy",
    "today", "tomorrow", "el", "la", "los", "las", "un", "una", "de",
    "para", "por", "con", "una", "tarde", "noche", "mañana", "a", "las",
    "lunes","martes","miercoles","miércoles","jueves","viernes","sábado","sabado","domingo",
    "hacer", "recordar", "remind", "me", "mi",
}


def parse_life_text(text: str) -> Dict[str, Any]:
    """Parse free-form text into a typed life-task dict."""
    norm = _normalize(text)

    task_type = "reminder"
    for kw in _PAYMENT_KWS:
        if kw in norm:
            task_type = "payment"
            break
    if task_type == "reminder":
        for kw in _CALL_KWS:
            if kw in norm:
                task_type = "call"
                break
    if task_type == "reminder":
        for kw in _SHOPPING_KWS:
            if kw in norm:
                task_type = "shopping"
                break

    due   = _parse_due(text)
    title = _clean_title(text, task_type)

    # Extract amount for payments
    amount = None
    if task_type == "payment":
        m = re.search(r"\$?\s*([\d.,]+)\s*(?:mil|k)?", norm)
        if m:
            raw = m.group(1).replace(",", "").replace(".", "")
            amount = float(raw)
            if "mil" in norm[m.end():m.end()+5] or "k" in norm[m.end():m.end()+3]:
                amount *= 1000

    # Extract contact for calls
    contact = None
    if task_type == "call":
        for kw in _CALL_KWS:
            if kw in norm:
                after = norm.split(kw, 1)[-1].strip()
                contact = after.split()[0].capitalize() if after else None
                break

    return {
        "type":    task_type,
        "title":   title,
        "due":     due,
        "amount":  amount,
        "contact": contact,
        "raw":     text,
    }


def _normalize(s: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _clean_title(text: str, task_type: str) -> str:
    """Strip noise words and produce a clean task title."""
    words = text.split()
    # Remove leading verbs/fillers
    filler_start = {"tengo", "debo", "hay", "necesito", "que", "recordar",
                    "remind", "me", "hacer", "pagar", "pay", "comprar", "buy",
                    "llamar", "call", "hablar"}
    while words and _normalize(words[0]) in filler_start:
        words = words[1:]
    # Remove trailing time phrases
    for pat in [r"mañana", r"manana", r"hoy", r"el (lunes|martes|miercoles|jueves|viernes)",
                r"a las? \d+", r"esta semana", r"en \d+ dias?"]:
        words = [w for w in words if not re.fullmatch(pat, _normalize(w))]
    title = " ".join(words).strip()
    if not title:
        title = text.strip()
    # Capitalise
    return title[:1].upper() + title[1:] if title else text


# ── Engine ────────────────────────────────────────────────────────────────

class LifeEngine:
    MODULES = ("reminders", "shopping", "calls", "payments")

    def __init__(self, base_dir: str, user_id: str = "owner") -> None:
        self._base = Path(base_dir)
        self._user = user_id
        self._lock = threading.Lock()
        self._base.mkdir(parents=True, exist_ok=True)
        for module in self.MODULES:
            p = self._path(module)
            if not p.exists():
                self._write(module, {"items": []})

    # ── Reminders ────────────────────────────────────────────────────────

    def add_reminder(self, title: str, due: str,
                     repeat: Optional[str] = None, notes: str = "") -> Dict:
        return self._append("reminders", {
            "id": _gen_id(), "title": title, "due": due,
            "repeat": repeat, "notes": notes, "done": False, "created_at": _now(),
        })

    def get_reminders(self, include_done: bool = False) -> List[Dict]:
        items = self._read("reminders")["items"]
        if not include_done:
            items = [i for i in items if not i.get("done")]
        return sorted(items, key=lambda x: x.get("due", ""))

    def complete_reminder(self, item_id: str) -> Optional[Dict]:
        return self._set_done("reminders", item_id)

    def delete_reminder(self, item_id: str) -> bool:
        return self._delete("reminders", item_id)

    def check_due(self) -> List[Dict]:
        """Items due within the next 60 seconds — used by the scheduler."""
        now = datetime.utcnow()
        window = now + timedelta(seconds=65)
        result = []
        for item in self.get_reminders():
            try:
                if now <= datetime.fromisoformat(item["due"]) <= window:
                    result.append(item)
            except Exception:
                pass
        return result

    # ── Shopping ─────────────────────────────────────────────────────────

    def add_shopping(self, name: str, qty: int = 1,
                     category: str = "general", notes: str = "") -> Dict:
        return self._append("shopping", {
            "id": _gen_id(), "name": name, "qty": qty,
            "category": category, "notes": notes,
            "checked": False, "created_at": _now(),
        })

    def get_shopping(self) -> List[Dict]:
        items = self._read("shopping")["items"]
        return sorted(items, key=lambda x: (x.get("checked", False), x.get("category", "")))

    def toggle_shopping(self, item_id: str) -> Optional[Dict]:
        with self._lock:
            d = self._read("shopping")
            for item in d["items"]:
                if item["id"] == item_id:
                    item["checked"] = not item.get("checked", False)
                    self._write("shopping", d)
                    return item
        return None

    def delete_shopping(self, item_id: str) -> bool:
        return self._delete("shopping", item_id)

    def clear_checked(self) -> int:
        with self._lock:
            d = self._read("shopping")
            before = len(d["items"])
            d["items"] = [i for i in d["items"] if not i.get("checked")]
            self._write("shopping", d)
            return before - len(d["items"])

    # ── Calls ─────────────────────────────────────────────────────────────

    def add_call(self, contact: str, due: str,
                 notes: str = "", phone: str = "") -> Dict:
        return self._append("calls", {
            "id": _gen_id(), "contact": contact, "due": due,
            "notes": notes, "phone": phone, "done": False, "created_at": _now(),
        })

    def get_calls(self, include_done: bool = False) -> List[Dict]:
        items = self._read("calls")["items"]
        if not include_done:
            items = [i for i in items if not i.get("done")]
        return sorted(items, key=lambda x: x.get("due", ""))

    def complete_call(self, item_id: str) -> Optional[Dict]:
        return self._set_done("calls", item_id)

    def delete_call(self, item_id: str) -> bool:
        return self._delete("calls", item_id)

    # ── Payments ──────────────────────────────────────────────────────────

    def add_payment(self, title: str, amount: float, due: str,
                    recurrence: Optional[str] = None, currency: str = "COP") -> Dict:
        return self._append("payments", {
            "id": _gen_id(), "title": title, "amount": amount,
            "currency": currency, "due": due, "recurrence": recurrence,
            "done": False, "created_at": _now(),
        })

    def get_payments(self, include_done: bool = False) -> List[Dict]:
        items = self._read("payments")["items"]
        if not include_done:
            items = [i for i in items if not i.get("done")]
        return sorted(items, key=lambda x: x.get("due", ""))

    def complete_payment(self, item_id: str) -> Optional[Dict]:
        return self._set_done("payments", item_id)

    def delete_payment(self, item_id: str) -> bool:
        return self._delete("payments", item_id)

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        return {
            "reminders_pending": len(self.get_reminders()),
            "shopping_unchecked": len([i for i in self.get_shopping() if not i.get("checked")]),
            "calls_pending":      len(self.get_calls()),
            "payments_pending":   len(self.get_payments()),
        }

    # ── Storage ───────────────────────────────────────────────────────────

    def _path(self, module: str) -> Path:
        return self._base / f"{self._user}_{module}.json"

    def _read(self, module: str) -> Dict:
        try:
            return json.loads(self._path(module).read_text(encoding="utf-8"))
        except Exception:
            return {"items": []}

    def _write(self, module: str, data: Dict) -> None:
        self._path(module).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append(self, module: str, item: Dict) -> Dict:
        with self._lock:
            d = self._read(module)
            d["items"].append(item)
            if len(d["items"]) > 500:
                d["items"] = d["items"][-400:]
            self._write(module, d)
        return item

    def _set_done(self, module: str, item_id: str) -> Optional[Dict]:
        with self._lock:
            d = self._read(module)
            for item in d["items"]:
                if item["id"] == item_id:
                    item["done"] = True
                    item["completed_at"] = _now()
                    self._write(module, d)
                    return item
        return None

    def _delete(self, module: str, item_id: str) -> bool:
        with self._lock:
            d = self._read(module)
            before = len(d["items"])
            d["items"] = [i for i in d["items"] if i["id"] != item_id]
            if len(d["items"]) < before:
                self._write(module, d)
                return True
        return False
