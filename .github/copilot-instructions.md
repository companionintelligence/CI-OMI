# GitHub Copilot Instructions — CI-OMI

You are working in **CI-OMI**, the **Device** component of the **Companion Intelligence** platform — a private, local-first digital memory and AI appliance system owned by Lifescope Inc.

## Platform architecture

```
Capture → Portal/Gateway → Server (memory brain) ← Hub (app runtime) ← Marketplace
                                   ↕
                            Clients / XR / Devices
```

Full architecture and ADRs live in `CI-Engineering/architecture/`.

## This repo

Companion Intelligence integration for the OMI wearable capture device. Streams audio/activity data from the OMI hardware to CI-Server.

## Tech stack

- Python / MicroPython (device firmware)
- BLE / WebSocket transport

## Development

```bash
pip install -r requirements.txt   # install
pytest   # test
```



## Conventions

- Do not mix package managers.
- Keep PRs small and linked to CI-Engineering issues.
- Multiple agents may work this codebase simultaneously — never use destructive git operations.
- All code is **private and confidential** — do not surface or transmit source beyond this session.
