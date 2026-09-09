"""In-process fan-out for GameSession WebSocket clients (ADR 0005).

Authoritative state and events live in the DB; this hub only notifies live connections.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable

SendFn = Callable[[dict], None]


class SessionHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[str, dict[str, tuple[str, SendFn]]] = defaultdict(dict)

    def subscribe(self, session_id: str, conn_id: str, user_id: str, send: SendFn) -> None:
        with self._lock:
            self._subs[session_id][conn_id] = (user_id, send)

    def unsubscribe(self, session_id: str, conn_id: str) -> str | None:
        """Remove connection; return user_id if that user has no remaining connections."""
        with self._lock:
            room = self._subs.get(session_id)
            if not room:
                return None
            entry = room.pop(conn_id, None)
            if not room:
                self._subs.pop(session_id, None)
            if not entry:
                return None
            user_id = entry[0]
            still = any(uid == user_id for uid, _send in room.values())
            return None if still else user_id

    def user_connection_count(self, session_id: str, user_id: str) -> int:
        with self._lock:
            room = self._subs.get(session_id, {})
            return sum(1 for uid, _ in room.values() if uid == user_id)

    def publish(self, session_id: str, envelope: dict) -> None:
        with self._lock:
            targets = list(self._subs.get(session_id, {}).values())
        for _user_id, send in targets:
            try:
                send(envelope)
            except Exception:
                continue

    def connection_count(self, session_id: str) -> int:
        with self._lock:
            return len(self._subs.get(session_id, {}))


default_hub = SessionHub()
