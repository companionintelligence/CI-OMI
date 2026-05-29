# AGENTS.md — CI-OMI

## Platform context

CI-OMI is the **Device** layer component of the Companion Intelligence platform — a private, local-first digital memory system.

Full architecture: `CI-Engineering/architecture/architecture.md`

## Repo summary

Companion Intelligence integration for the OMI wearable capture device. Streams audio/activity data from the OMI hardware to CI-Server.

## Stack

- Python / MicroPython (device firmware)
- BLE / WebSocket transport

## Setup & commands

```bash
pip install -r requirements.txt   # install
python main.py   # dev
pytest   # test
# firmware flash via device toolchain   # build
```



## Git discipline

- Never `git reset --hard` or `git clean -f` without user confirmation.
- Commit messages: imperative mood, ≤ 72 chars.
- Reference CI-Engineering issues in PRs (e.g. `Closes companionintelligence/CI-Engineering#32`).

## Confidentiality

Private & Confidential — Property of Lifescope Inc. Do not distribute.
