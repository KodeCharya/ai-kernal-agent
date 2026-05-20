"""Real-time log collector for kernel and system logs."""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from config import DEMO_INTERVAL_SECONDS, DEMO_LOGS, ENABLE_DEMO_STREAM, LOG_COMMANDS


@dataclass
class LogEntry:
    """Represents one collected log line."""

    timestamp: str
    source: str
    message: str


class LogCollector:
    """Collects logs from multiple Linux sources in background threads."""

    def __init__(self, max_queue_size: int = 4000) -> None:
        self._queue: queue.Queue[LogEntry] = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._processes: list[subprocess.Popen] = []
        self._dropped_lines = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start all configured log streams."""
        self._stop_event.clear()
        self._start_command_streams()
        if ENABLE_DEMO_STREAM:
            self._start_demo_stream()

    def stop(self) -> None:
        """Stop all streams and cleanup child processes."""
        self._stop_event.set()
        for proc in self._processes:
            if proc.poll() is None:
                proc.terminate()
        for thread in self._threads:
            thread.join(timeout=2.0)
        self._threads.clear()
        self._processes.clear()

    def get_entry(self, timeout: float = 1.0) -> Optional[LogEntry]:
        """Return one log entry if available."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def dropped_count(self) -> int:
        """Return how many entries were dropped due to backpressure."""
        with self._lock:
            return self._dropped_lines

    def _start_command_streams(self) -> None:
        for source, command in LOG_COMMANDS.items():
            if not shutil.which(command[0]):
                continue
            thread = threading.Thread(
                target=self._stream_command, args=(source, command), daemon=True
            )
            self._threads.append(thread)
            thread.start()

    def _stream_command(self, source: str, command: Iterable[str]) -> None:
        try:
            proc = subprocess.Popen(
                list(command), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
        except OSError as exc:
            self._enqueue(source, f"collector error: {exc}")
            return
        self._processes.append(proc)
        self._read_process_output(source, proc)

    def _read_process_output(self, source: str, proc: subprocess.Popen) -> None:
        if not proc.stdout:
            return
        for line in proc.stdout:
            if self._stop_event.is_set():
                break
            text = line.strip()
            if text:
                self._enqueue(source, text)

    def _start_demo_stream(self) -> None:
        thread = threading.Thread(target=self._emit_demo_logs, daemon=True)
        self._threads.append(thread)
        thread.start()

    def _emit_demo_logs(self) -> None:
        while not self._stop_event.is_set():
            for line in DEMO_LOGS:
                if self._stop_event.is_set():
                    return
                self._enqueue("demo", line)
                time.sleep(DEMO_INTERVAL_SECONDS)

    def _enqueue(self, source: str, message: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        entry = LogEntry(timestamp=stamp, source=source, message=message)
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            self._drop_oldest_and_insert(entry)

    def _drop_oldest_and_insert(self, entry: LogEntry) -> None:
        with self._lock:
            self._dropped_lines += 1
        try:
            _ = self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            pass
