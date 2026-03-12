from dataclasses import dataclass
from typing import Any
import time
import uuid

@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    source: str
    payload: Any
    timestamp: float
    confidence: float | None = None

    @staticmethod
    def create(event_type, source, payload, confidence=None):
        return Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            payload=payload,
            timestamp=time.time(),
            confidence=confidence
        )