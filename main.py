"""CLI entry point for AI Kernel Error Monitoring & Auto-Healing."""

from __future__ import annotations

import signal
import threading
from datetime import datetime, timezone

from classifier import Detection, ErrorDetectionPipeline
from config import DB_PATH, MAX_QUEUE_SIZE, MODEL_NAME
from fixer import FixPlan, Fixer
from log_collector import LogCollector
from model import TransformerErrorModel
from utils import SQLiteStore


class KernelAgentApp:
    """Coordinates collection, detection, recommendations, and user actions."""

    def __init__(self) -> None:
        self.store = SQLiteStore(DB_PATH)
        self.collector = LogCollector(max_queue_size=MAX_QUEUE_SIZE)
        self.model = TransformerErrorModel(model_name=MODEL_NAME)
        self.fixer = Fixer()
        self.pipeline = ErrorDetectionPipeline(self.model, self.fixer, self.store)
        self._active = False
        self._worker: threading.Thread | None = None

    def start_monitoring(self) -> None:
        if self._active:
            print("Monitoring is already running.")
            return
        self._active = True
        self.collector.start()
        self._worker = threading.Thread(target=self._consume_logs, daemon=True)
        self._worker.start()
        print("Monitoring started. Collecting logs from journalctl, dmesg, syslog, demo.")

    def stop(self) -> None:
        self._active = False
        self.collector.stop()
        if self._worker:
            self._worker.join(timeout=2.0)
        self.store.close()
        print("Agent stopped.")

    def run(self) -> None:
        self.start_monitoring()
        self._print_help()
        while True:
            try:
                command = input("agent> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not self._handle_command(command):
                break
        self.stop()

    def _consume_logs(self) -> None:
        while self._active:
            entry = self.collector.get_entry(timeout=1.0)
            if not entry:
                continue
            self.store.insert_raw_log(entry.timestamp, entry.source, entry.message)
            detection = self.pipeline.process(entry)
            if detection.error_type != "Unknown":
                self._print_detection(detection)

    def _handle_command(self, command: str) -> bool:
        if not command:
            return True
        if command == "start monitoring":
            self.start_monitoring()
            return True
        if command == "show detected errors":
            self._show_detections()
            return True
        if command.startswith("apply fix"):
            self._apply_fix(command)
            return True
        if command in {"exit", "quit"}:
            return False
        if command == "help":
            self._print_help()
            return True
        print("Unknown command. Use: start monitoring | show detected errors | apply fix <id> | exit")
        return True

    def _show_detections(self) -> None:
        items = self.pipeline.recent(limit=15)
        if not items:
            print("No detections yet.")
            return
        for item in items:
            print(
                f"[{item.id}] {item.error_type} conf={item.confidence:.2f} "
                f"src={item.source} msg={item.raw_log[:90]}"
            )
            print(f"  Recommendation: {item.recommendation}")

    def _apply_fix(self, command: str) -> None:
        parts = command.split()
        if len(parts) < 3:
            print("Usage: apply fix <detection_id>")
            return
        detection = self.pipeline.find(parts[2])
        if not detection:
            print(f"Detection '{parts[2]}' not found in memory.")
            return
        plan = FixPlan(detection.error_type, detection.recommendation, detection.fix_command)
        if not plan.command:
            print(f"No auto-fix for {detection.error_type}.")
            return
        print(f"Proposed command: {' '.join(plan.command)}")
        choice = input("Approve execution? [y/N]: ").strip().lower()
        if choice != "y":
            print("Fix cancelled.")
            return
        success, output = self.fixer.execute(plan)
        stamp = datetime.now(timezone.utc).isoformat()
        self.store.insert_action(stamp, detection.id, " ".join(plan.command), success, output)
        print("Fix succeeded." if success else "Fix failed.")
        print(output[:500])

    def _print_detection(self, detection: Detection) -> None:
        print(
            f"\n[DETECTED] id={detection.id} type={detection.error_type} "
            f"confidence={detection.confidence:.2f}"
        )
        print(f"log: {detection.raw_log}")
        print(f"recommendation: {detection.recommendation}\n")

    def _print_help(self) -> None:
        print("Commands: start monitoring | show detected errors | apply fix <id> | help | exit")


def _install_signal_handlers(app: KernelAgentApp) -> None:
    def _handler(_: int, __: object) -> None:
        app.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


if __name__ == "__main__":
    application = KernelAgentApp()
    _install_signal_handlers(application)
    application.run()
