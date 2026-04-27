"""Helper: append Life Automation endpoints to main.py"""
code = r'''

# ══════════════════════════════════════════════════════════════════════
# LIFE AUTOMATION SYSTEM  (Phase 6Z-4)
# ══════════════════════════════════════════════════════════════════════

import asyncio as _asyncio
from core.life_engine import LifeEngine as _LifeEngine, parse_life_text as _parse_life_text

_life_cache: dict = {}

def _life(user_id: str) -> _LifeEngine:
    if user_id not in _life_cache:
        path = BASE_DIR / "data" / "life" / user_id
        _life_cache[user_id] = _LifeEngine(str(path), user_id)
    return _life_cache[user_id]


class _LifeTaskReq(BaseModel):
    text: str

class _ReminderReq(BaseModel):
    title: str
    due: str
    repeat: Optional[str] = None
    notes: str = ""

class _ShoppingReq(BaseModel):
    name: str
    qty: int = 1
    category: str = "general"
    notes: str = ""

class _CallReq(BaseModel):
    contact: str
    due: str
    notes: str = ""
    phone: str = ""

class _PaymentReq(BaseModel):
    title: str
    amount: float
    due: str
    recurrence: Optional[str] = None
    currency: str = "COP"


@app.post("/api/life/task")
def life_task(body: _LifeTaskReq, current_user: dict = Depends(get_optional_user)):
    uid    = current_user["user_id"]
    parsed = _parse_life_text(body.text)
    engine = _life(uid)
    created = []

    if parsed["type"] == "payment":
        item = engine.add_payment(parsed["title"], parsed["amount"] or 0.0, parsed["due"])
        created.append({"module": "payment", "item": item})
        try:
            from datetime import datetime as _dt, timedelta as _td
            remind_dt = (_dt.fromisoformat(parsed["due"]) - _td(days=1)).isoformat()
            rem = engine.add_reminder(f"Pagar: {parsed['title']}", remind_dt)
            created.append({"module": "reminder", "item": rem})
        except Exception:
            pass
    elif parsed["type"] == "call":
        item = engine.add_call(parsed["contact"] or parsed["title"], parsed["due"], parsed["raw"])
        created.append({"module": "call", "item": item})
    elif parsed["type"] == "shopping":
        item = engine.add_shopping(name=parsed["title"])
        created.append({"module": "shopping", "item": item})
    else:
        item = engine.add_reminder(parsed["title"], parsed["due"], notes=parsed["raw"])
        created.append({"module": "reminder", "item": item})

    return {"status": "ok", "parsed": parsed, "created": created}


@app.post("/api/life/reminder")
def add_reminder(body: _ReminderReq, current_user: dict = Depends(get_optional_user)):
    from core.life_engine import _parse_due
    due = body.due if "T" in body.due else _parse_due(body.due)
    item = _life(current_user["user_id"]).add_reminder(body.title, due, body.repeat, body.notes)
    return {"status": "ok", "item": item}

@app.get("/api/life/reminders")
def get_reminders(include_done: bool = False, current_user: dict = Depends(get_optional_user)):
    items = _life(current_user["user_id"]).get_reminders(include_done)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/life/reminder/{item_id}/done")
def complete_reminder(item_id: str, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).complete_reminder(item_id)
    if not item: raise HTTPException(404, "Reminder not found")
    return {"status": "ok", "item": item}

@app.delete("/api/life/reminder/{item_id}")
def delete_reminder(item_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _life(current_user["user_id"]).delete_reminder(item_id)
    return {"status": "ok" if ok else "not_found"}


@app.post("/api/life/shopping")
def add_shopping(body: _ShoppingReq, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).add_shopping(body.name, body.qty, body.category, body.notes)
    return {"status": "ok", "item": item}

@app.get("/api/life/shopping")
def get_shopping(current_user: dict = Depends(get_optional_user)):
    items = _life(current_user["user_id"]).get_shopping()
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/life/shopping/{item_id}/toggle")
def toggle_shopping(item_id: str, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).toggle_shopping(item_id)
    if not item: raise HTTPException(404, "Item not found")
    return {"status": "ok", "item": item}

@app.delete("/api/life/shopping/{item_id}")
def delete_shopping(item_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _life(current_user["user_id"]).delete_shopping(item_id)
    return {"status": "ok" if ok else "not_found"}

@app.post("/api/life/shopping/clear-checked")
def clear_checked_shopping(current_user: dict = Depends(get_optional_user)):
    n = _life(current_user["user_id"]).clear_checked()
    return {"status": "ok", "cleared": n}


@app.post("/api/life/call")
def add_call(body: _CallReq, current_user: dict = Depends(get_optional_user)):
    from core.life_engine import _parse_due
    due = body.due if "T" in body.due else _parse_due(body.due)
    item = _life(current_user["user_id"]).add_call(body.contact, due, body.notes, body.phone)
    return {"status": "ok", "item": item}

@app.get("/api/life/calls")
def get_calls(include_done: bool = False, current_user: dict = Depends(get_optional_user)):
    items = _life(current_user["user_id"]).get_calls(include_done)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/life/call/{item_id}/done")
def complete_call(item_id: str, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).complete_call(item_id)
    if not item: raise HTTPException(404, "Call not found")
    return {"status": "ok", "item": item}

@app.delete("/api/life/call/{item_id}")
def delete_call(item_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _life(current_user["user_id"]).delete_call(item_id)
    return {"status": "ok" if ok else "not_found"}


@app.post("/api/life/payment")
def add_payment(body: _PaymentReq, current_user: dict = Depends(get_optional_user)):
    from core.life_engine import _parse_due
    due = body.due if "T" in body.due else _parse_due(body.due)
    item = _life(current_user["user_id"]).add_payment(
        body.title, body.amount, due, body.recurrence, body.currency)
    return {"status": "ok", "item": item}

@app.get("/api/life/payments")
def get_payments(include_done: bool = False, current_user: dict = Depends(get_optional_user)):
    items = _life(current_user["user_id"]).get_payments(include_done)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/life/payment/{item_id}/done")
def complete_payment(item_id: str, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).complete_payment(item_id)
    if not item: raise HTTPException(404, "Payment not found")
    return {"status": "ok", "item": item}

@app.delete("/api/life/payment/{item_id}")
def delete_payment(item_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _life(current_user["user_id"]).delete_payment(item_id)
    return {"status": "ok" if ok else "not_found"}


@app.get("/api/life/summary")
def life_summary(current_user: dict = Depends(get_optional_user)):
    return {"status": "ok", **_life(current_user["user_id"]).summary()}


async def _reminder_scheduler() -> None:
    while True:
        try:
            engine = _life("owner")
            for item in engine.check_due():
                try:
                    _notif("owner").create(
                        title=f"Recordatorio: {item['title']}",
                        message=item.get("notes", ""),
                        notif_type="reminder",
                        priority="high",
                        action_url="life",
                    )
                    engine.complete_reminder(item["id"])
                except Exception:
                    pass
        except Exception:
            pass
        await _asyncio.sleep(60)


@app.on_event("startup")
async def _start_scheduler() -> None:
    _asyncio.create_task(_reminder_scheduler())
'''

with open("c:/Users/juanc/JARVIS/main.py", "a", encoding="utf-8") as f:
    f.write(code)
print("appended ok")
