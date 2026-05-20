"""Real-time error detection pipeline."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import Optional
from uuid import uuid4

from config import DETECTION_THRESHOLD, MAX_DETECTIONS_IN_MEMORY
from fixer import FixPlan, Fixer
from log_collector import LogEntry
from model import TransformerErrorModel
from utils import SQLiteStore, clean_log_line


@dataclass
class Detection:
    """One classified detection event."""

    id: str
    timestamp: str
    source: str
    raw_log: str
    cleaned_log: str
    error_type: str
    confidence: float
    scores: dict[str, float]
    recommendation: str
    fix_command: list[str]


class ErrorDetectionPipeline:
    """Classifies incoming logs and stores detection results."""

    def __init__(
        self,
        model: TransformerErrorModel,
        fixer: Fixer,
        store: SQLiteStore,
        threshold: float = DETECTION_THRESHOLD,
        max_cache: int = MAX_DETECTIONS_IN_MEMORY,
    ) -> None:
        self.model = model
        self.fixer = fixer
        self.store = store
        self.threshold = threshold
        self._detections: deque[Detection] = deque(maxlen=max_cache)

    def process(self, entry: LogEntry) -> Detection:
        cleaned = clean_log_line(entry.message)
        label, confidence, scores = self.model.predict(cleaned)
        if confidence < self.threshold:
            label = "Unknown"
        fix = self.fixer.recommend(label, entry.message)
        detection = self._build_detection(entry, cleaned, label, confidence, scores, fix)
        self._detections.appendleft(detection)
        self.store.insert_detection(asdict(detection))
        return detection

    def recent(self, limit: int = 20) -> list[Detection]:
        return list(self._detections)[:limit]

    def find(self, detection_id: str) -> Optional[Detection]:
        for item in self._detections:
            if item.id == detection_id:
                return item
        return None

    def _build_detection(
        self,
        entry: LogEntry,
        cleaned: str,
        label: str,
        confidence: float,
        scores: dict[str, float],
        fix: FixPlan,
    ) -> Detection:
        return Detection(
            id=str(uuid4())[:8],
            timestamp=entry.timestamp,
            source=entry.source,
            raw_log=entry.message,
            cleaned_log=cleaned,
            error_type=label,
            confidence=confidence,
            scores=scores,
            recommendation=fix.summary,
            fix_command=fix.command,
        )
