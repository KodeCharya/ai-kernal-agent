"""Fix recommendation and safe execution module."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from config import SCRIPTS_DIR
from utils import extract_service_name


@dataclass
class FixPlan:
    """Represents a recommended fix action."""

    error_type: str
    summary: str
    command: list[str] = field(default_factory=list)


class Fixer:
    """Maps error classes to safe, user-space fix scripts."""

    def __init__(self, scripts_dir: Path = SCRIPTS_DIR) -> None:
        self.scripts_dir = scripts_dir
        self._commands = {
            "Disk Error": self._disk_fix,
            "Network Error": self._network_fix,
            "Service Crash": self._service_fix,
            "Memory Error": self._memory_fix,
            "Driver Error": self._driver_fix,
            "Kernel Panic": self._panic_fix,
        }

    def recommend(self, error_type: str, message: str) -> FixPlan:
        builder = self._commands.get(error_type, self._unknown_fix)
        return builder(message)

    def execute(self, plan: FixPlan) -> tuple[bool, str]:
        if not plan.command:
            return False, "No executable auto-fix command available."
        if not self._safe_command(plan.command):
            return False, "Blocked: command is outside approved script directory."
        try:
            result = subprocess.run(
                plan.command, capture_output=True, text=True, timeout=120, check=False
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"Execution failed: {exc}"
        output = (result.stdout + "\n" + result.stderr).strip()
        return result.returncode == 0, output or "(no output)"

    def _safe_command(self, command: list[str]) -> bool:
        if not command:
            return False
        script = Path(command[0]).resolve()
        return script.is_file() and script.parent == self.scripts_dir.resolve()

    def _disk_fix(self, _: str) -> FixPlan:
        command = [str(self.scripts_dir / "fsck_preview.sh")]
        return FixPlan("Disk Error", "Preview filesystem repair with fsck -N.", command)

    def _network_fix(self, _: str) -> FixPlan:
        command = [str(self.scripts_dir / "restart_network.sh")]
        return FixPlan("Network Error", "Restart active network service.", command)

    def _service_fix(self, message: str) -> FixPlan:
        service = extract_service_name(message)
        if not service:
            return FixPlan("Service Crash", "Service name missing; restart manually.")
        command = [str(self.scripts_dir / "restart_service.sh"), service]
        return FixPlan("Service Crash", f"Restart crashed service: {service}.", command)

    def _memory_fix(self, _: str) -> FixPlan:
        return FixPlan("Memory Error", "Inspect OOM logs and reduce memory pressure.")

    def _driver_fix(self, _: str) -> FixPlan:
        return FixPlan("Driver Error", "Check module/firmware versions before reload.")

    def _panic_fix(self, _: str) -> FixPlan:
        return FixPlan("Kernel Panic", "Collect crash dump and reboot via maintenance plan.")

    def _unknown_fix(self, _: str) -> FixPlan:
        return FixPlan("Unknown", "No automatic fix available.")
