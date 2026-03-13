from dataclasses import dataclass
import time
import uuid

@dataclass(frozen=True)
class Intent:
    intent_id: str
    action: str
    target: str | None
    source_event_id: str
    timestamp: float
    raw_text: str = ""

    @staticmethod
    def create(action, target, source_event_id, raw_text=""):
        return Intent(
            intent_id=str(uuid.uuid4()),
            action=action,
            target=target,
            source_event_id=source_event_id,
            timestamp=time.time(),
            raw_text=raw_text
        )