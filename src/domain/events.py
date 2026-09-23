"""Thread-safe application events without a dependency on any UI toolkit."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """A serializable event emitted by the application runtime."""

    type: str
    data: Any = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(
                self,
                "timestamp",
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.type, "data": self.data, "timestamp": self.timestamp}


class EventSubscription:
    """Async queue owned by one WebSocket client."""

    def __init__(self, broker: "EventBroker", loop: asyncio.AbstractEventLoop, maxsize: int) -> None:
        self._broker = broker
        self._loop = loop
        self._queue: asyncio.Queue[RuntimeEvent] = asyncio.Queue(maxsize=maxsize)
        self._closed = False

    async def next_event(self) -> RuntimeEvent:
        if self._closed:
            raise RuntimeError("Event subscription is closed")
        return await self._queue.get()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._broker.unsubscribe(self)

    def _enqueue(self, event: RuntimeEvent) -> None:
        """Offer an event from the subscriber's asyncio loop."""
        if self._closed:
            return
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._queue.put_nowait(event)


class EventBroker:
    """Fan out runtime events from arbitrary threads to asyncio consumers."""

    def __init__(self, *, queue_size: int = 128) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        self._queue_size = queue_size
        self._lock = RLock()
        self._subscriptions: set[EventSubscription] = set()

    def publish(self, event_type: str, data: Any = None) -> RuntimeEvent:
        event = RuntimeEvent(type=event_type, data=data)
        with self._lock:
            subscriptions = tuple(self._subscriptions)
        for subscription in subscriptions:
            if subscription._closed:
                continue
            try:
                subscription._loop.call_soon_threadsafe(subscription._enqueue, event)
            except RuntimeError:
                # The consumer loop may close between the snapshot and dispatch.
                subscription.close()
        return event

    def subscribe(self) -> EventSubscription:
        loop = asyncio.get_running_loop()
        subscription = EventSubscription(self, loop, self._queue_size)
        with self._lock:
            self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: EventSubscription) -> None:
        with self._lock:
            self._subscriptions.discard(subscription)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)
