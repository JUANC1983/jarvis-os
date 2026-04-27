"""
Async event queue — decouples webhook receipt from processing.
Webhook handlers enqueue events and return immediately (<2s).
Background worker processes events without blocking the web server.
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional

log = logging.getLogger("jarvis.event_queue")


class EventQueue:
    def __init__(self, max_size: int = 1000) -> None:
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._handlers: Dict[str, Callable[..., Coroutine]] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._processed = 0
        self._errors = 0
        self._type_counts: Counter = Counter()

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, event_type: str, handler: Callable[..., Coroutine]) -> None:
        """Register an async handler for a named event type."""
        self._handlers[event_type] = handler
        log.debug("Handler registered for event type: %s", event_type)

    # ── Producer side ─────────────────────────────────────────────────────

    async def enqueue(self, event_type: str, payload: Any) -> bool:
        """
        Put an event on the queue. Non-blocking with 0.5s timeout.
        Returns False if queue is full (event dropped).
        """
        event = {
            "type":    event_type,
            "payload": payload,
            "queued_at": datetime.utcnow().isoformat(),
        }
        try:
            await asyncio.wait_for(self._queue.put(event), timeout=0.5)
            log.debug("Enqueued %s (queue depth: %d)", event_type, self._queue.qsize())
            return True
        except asyncio.TimeoutError:
            log.warning("Event queue full — dropping %s event (qsize=%d)", event_type, self._queue.qsize())
            return False
        except Exception as exc:
            log.error("enqueue error for %s: %s", event_type, exc)
            return False

    # ── Worker ────────────────────────────────────────────────────────────

    async def _worker(self) -> None:
        log.info("Event queue worker started (max_size=%d)", self._queue.maxsize)
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                etype   = event.get("type", "unknown")
                handler = self._handlers.get(etype)
                if handler:
                    try:
                        await handler(event["payload"])
                        self._processed += 1
                        self._type_counts[etype] += 1
                    except Exception as exc:
                        self._errors += 1
                        log.error("Handler error [%s]: %s", etype, exc, exc_info=True)
                else:
                    log.warning("No handler registered for event type: %s", etype)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("Worker loop error: %s", exc)
        log.info("Event queue worker stopped (processed=%d errors=%d)", self._processed, self._errors)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background worker. Call from FastAPI lifespan / startup."""
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        """Drain queue and stop the worker gracefully."""
        self._running = False
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=10.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._worker_task.cancel()

    # ── Observability ─────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        return {
            "running":    self._running,
            "queue_size": self._queue.qsize(),
            "processed":  self._processed,
            "errors":     self._errors,
            "by_type":    dict(self._type_counts),
        }

    def pending_items(self) -> List[Dict]:
        """Snapshot of items currently in the queue (does not drain it)."""
        return list(self._queue._queue)  # type: ignore[attr-defined]


# Singleton — imported by main.py and webhook handler
event_queue = EventQueue()
