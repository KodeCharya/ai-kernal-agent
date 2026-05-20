"""Configuration constants for AI kernel monitoring agent."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "kernel_agent.db"
SCRIPTS_DIR = BASE_DIR / "fixes"

MODEL_NAME = "distilbert-base-uncased"
LABELS = [
    "Disk Error",
    "Memory Error",
    "Driver Error",
    "Network Error",
    "Kernel Panic",
    "Service Crash",
    "Unknown",
]

LABEL_PROTOTYPES = {
    "Disk Error": [
        "blk_update_request io error sector read failure",
        "ext4 filesystem corruption inode bitmap issue",
        "device sda failed command write error",
    ],
    "Memory Error": [
        "out of memory killer terminated process",
        "page allocation failure and memory pressure",
        "kernel reports memory corruption and fault",
    ],
    "Driver Error": [
        "driver failed to initialize hardware device",
        "module load failed with unknown symbol",
        "firmware missing causing driver malfunction",
    ],
    "Network Error": [
        "network interface link is down packet loss",
        "dns resolution failure and route unreachable",
        "connection timeout from network stack",
    ],
    "Kernel Panic": [
        "kernel panic not syncing fatal exception",
        "unable to handle kernel null pointer dereference",
        "watchdog hard lockup detected on cpu",
    ],
    "Service Crash": [
        "systemd service exited with failure status",
        "daemon crashed and restart request repeated",
        "service failed start job result failed",
    ],
    "Unknown": ["generic informational system log entry"],
}

LOG_COMMANDS = {
    "journalctl": ["journalctl", "-f", "-n", "0", "-o", "short-iso"],
    "dmesg": ["dmesg", "--follow", "--human"],
    "syslog": ["tail", "-Fn0", "/var/log/syslog"],
}

MAX_QUEUE_SIZE = 4000
MAX_DETECTIONS_IN_MEMORY = 200
DETECTION_THRESHOLD = 0.43
MODEL_TEMPERATURE = 0.6

ENABLE_DEMO_STREAM = True
DEMO_INTERVAL_SECONDS = 1.2
DEMO_LOGS = [
    "kernel: blk_update_request: I/O error, dev sda, sector 1209320",
    "systemd[1]: nginx.service: Main process exited, code=exited, status=1/FAILURE",
    "kernel: Out of memory: Killed process 1222 (python3) total-vm:512000kB",
    "NetworkManager[742]: <warn>  [169893.12] device (eth0): link disconnected",
    "kernel panic - not syncing: Fatal exception in interrupt",
]
