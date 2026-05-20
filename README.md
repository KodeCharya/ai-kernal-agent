# AI Kernel Error Monitoring & Auto-Healing Agent

Production-style user-space Linux monitoring tool that:
1. Streams logs from `journalctl`, `dmesg`, and `/var/log/syslog`
2. Cleans + classifies log lines using a DistilBERT-based transformer encoder
3. Recommends fixes by error class
4. Executes only approved local Bash fix scripts after user confirmation

## Project Layout

```text
ai-kernel-agent/
├── main.py
├── log_collector.py
├── model.py
├── classifier.py
├── fixer.py
├── utils.py
├── config.py
├── requirements.txt
├── data/
│   └── mock_logs.jsonl
└── fixes/
    ├── fsck_preview.sh
    ├── restart_network.sh
    └── restart_service.sh
```

## Requirements

- Ubuntu/Linux
- Python 3.10+
- Internet access on first run (to download `distilbert-base-uncased`)

## Run

```bash
cd ai-kernel-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The app auto-starts monitoring. Demo logs are enabled by default in `config.py` so detections appear immediately.

## CLI Commands

- `start monitoring`
- `show detected errors`
- `apply fix <detection_id>`
- `help`
- `exit`

## Example Input Logs

```text
kernel: blk_update_request: I/O error, dev sda, sector 1209320
systemd[1]: nginx.service: Main process exited, code=exited, status=1/FAILURE
NetworkManager[742]: <warn> device (eth0): link disconnected
kernel panic - not syncing: Fatal exception in interrupt
```

## Expected Runtime Output (sample)

```text
[DETECTED] id=5e32a7b8 type=Disk Error confidence=0.73
log: kernel: blk_update_request: I/O error, dev sda, sector 1209320
recommendation: Preview filesystem repair with fsck -N.

agent> show detected errors
[5e32a7b8] Disk Error conf=0.73 src=demo msg=kernel: blk_update_request...
  Recommendation: Preview filesystem repair with fsck -N.

agent> apply fix 5e32a7b8
Proposed command: /.../fixes/fsck_preview.sh
Approve execution? [y/N]:
```

## Notes

- The system operates entirely in user space.
- No shell strings are evaluated; commands are executed as argument lists.
- Fix execution is restricted to scripts in `fixes/`.
- For production deployment, disable demo logs by setting `ENABLE_DEMO_STREAM = False` in `config.py`.
