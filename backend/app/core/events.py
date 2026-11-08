import asyncio
import json
from datetime import datetime
from typing import Dict, Set, Any, Optional
from pydantic import BaseModel, Field

class AgentEvent(BaseModel):
    event_type: str = Field(..., description="token, tool_call_start, tool_call_result, approval_required, status, plan_update, error, done")
    conversation_id: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

class EventBus:
    """
    Manages in-memory event distribution to active WebSocket and SSE connections.
    """
    def __init__(self):
        # conversation_id -> set of asyncio.Queue
        self._listeners: Dict[str, Set[asyncio.Queue]] = {}
        # global listeners (e.g. status monitoring)
        self._global_listeners: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, conversation_id: Optional[str] = None) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=1000)
        async with self._lock:
            if conversation_id:
                if conversation_id not in self._listeners:
                    self._listeners[conversation_id] = set()
                self._listeners[conversation_id].add(q)
            else:
                self._global_listeners.add(q)
        return q

    async def unsubscribe(self, queue: asyncio.Queue, conversation_id: Optional[str] = None):
        async with self._lock:
            if conversation_id and conversation_id in self._listeners:
                self._listeners[conversation_id].discard(queue)
                if not self._listeners[conversation_id]:
                    del self._listeners[conversation_id]
            self._global_listeners.discard(queue)

    async def publish(self, event: AgentEvent):
        # Send to specific conversation listeners
        conv_id = event.conversation_id
        async with self._lock:
            targets = list(self._listeners.get(conv_id, []))
            global_targets = list(self._global_listeners)

        for q in targets:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # avoid lagging client locking server

        for q in global_targets:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

event_bus = EventBus()
