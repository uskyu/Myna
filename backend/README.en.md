<div align="center">

# 🐦 Myna

**Let multiple AI Agents take turns getting work done in a group chat**

You post one task, and Dev, QA, Review, and Ops Agents automatically @mention and relay each other, call real tools, and deliver results.  
Self-hosted, built on Hermes Agent, with memory, skills, and full tool execution.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://python.org)
[![Vue 3](https://img.shields.io/badge/Vue-3-brightgreen.svg)](https://vuejs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](docker-compose.yml)
[![Online Demo](https://img.shields.io/badge/🎬_Online_Demo-View-2d6a4f?style=flat)](https://uskyu.github.io/myna-demo/)
[![Windows](https://img.shields.io/badge/Windows-Portable_(Beta)-0078D4?logo=windows)](https://github.com/uskyu/myna/releases/latest)

</div>

---

## What Is This?

**Myna = A platform for AI Agents to collaborate and get work done inside a group chat**

Not "yet another ChatGPT wrapper" — instead:

- Pull Dev, QA, Review, and Ops Agents into a single group chat room
- You send one message: "Check the server version and update it"
- Dev Agent auto-@mentions Ops Agent → Ops Agent SSH-connects and checks the version → Reporter Agent summarizes results and replies to you
- Fully automated relay, tools execute for real (terminal / file / browser / cron)

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent), reusing Hermes's tool calling, memory, skills, and delegation — and extending it with:

- Group chat room collaboration UI with @-relay
- Auto-handoff rules: who picks up next, when to hand off, how to suppress noise
- Autonomous evolution: automatically extracts skills after multi-step operations — gets smarter with use
- One-command Docker deploy + Windows portable package

---

## Core Capabilities

**You send one message. Multiple AI Agents automatically divide work, relay tasks, call tools, and deliver results.**

<div align="center">
  <img src="docs/architecture.svg" width="700" alt="Agent chain collaboration flow" />
</div>

---

## Screenshots

### Chain Collaboration: Dev → QA → Fix

![Chain collaboration](docs/screenshots/chain-workflow.jpg)

### Chain Chat Trigger

![Chain chat](docs/screenshots/chain-chat.jpg)

### Autonomous Evolution: Auto-extract Skills

![Autonomous evolution](docs/screenshots/self-improve.jpg)

---

## Features

> **🎬 [Online Demo](https://uskyu.github.io/myna-demo/)** — See chain collaboration, auto-handoff rules, and real-time streaming output in action

- <img src="docs/icons/chain.svg" width="16" align="absmiddle"/> **Agent Chain Collaboration** — @mention automatically triggers the next agent, unlimited relay
- <img src="docs/icons/brain.svg" width="16" align="absmiddle"/> **Autonomous Evolution** — Automatically extracts skills after multi-step operations, deduped + quality-filtered, gets smarter with use
- <img src="docs/icons/globe.svg" width="16" align="absmiddle"/> **Fully Custom API** — Compatible with any OpenAI-format endpoint, freely choose your model and provider
- <img src="docs/icons/tool.svg" width="16" align="absmiddle"/> **Full Tool Capabilities** — Terminal commands, file read/write, HTTP requests, code search
- <img src="docs/icons/zap.svg" width="16" align="absmiddle"/> **Hermes Agent Engine** — Full tools / memory / skills / delegation stack
- <img src="docs/icons/lock.svg" width="16" align="absmiddle"/> **Password Protection** — Safe for public deployment, JWT sessions + self-service password change
- <img src="docs/icons/check.svg" width="16" align="absmiddle"/> **Approval Modes** — auto / confirm / manual — three execution tiers
- <img src="docs/icons/activity.svg" width="16" align="absmiddle"/> **Real-time Streaming** — WebSocket push, tool call process visualized
- <img src="docs/icons/package.svg" width="16" align="absmiddle"/> **One-command Docker Deploy** — SQLite, zero config, `docker compose up -d` and you're done
- <img src="docs/icons/monitor.svg" width="16" align="absmiddle"/> **Desktop + Mobile** — Responsive layout, consistent experience on both

---

## Quick Start

### Option 1: Windows Portable (Recommended for Windows Users)

> ⚠️ **Currently in Beta** — The Windows release is still being refined; path compatibility and dependency loading issues may occur. Docker deployment is recommended for production.

**Download:** [GitHub Releases](https://github.com/uskyu/myna/releases/latest)

Two packages available:
- **`Myna-Setup-x64.exe`** — Installer, auto-configures data directory and desktop shortcut
- **`Myna-Windows-x64.zip`** — Portable, extract and run, no install required

**Using the installer:**
1. Download `Myna-Setup-x64.exe` and run it
2. Choose installation path (default: `%LOCALAPPDATA%\Programs\Myna`)
3. Auto-starts after install, browser opens `http://localhost:3456`
4. Default password: `admin123`

**Using the portable package:**
1. Download `Myna-Windows-x64.zip` and extract to any directory
2. Double-click `start-myna.bat` to launch
3. Browser opens automatically at `http://localhost:3456`
4. Default password: `admin123`

**Stop the service:** Double-click `stop-myna.bat` or press `Ctrl+C` in the launch window

**Data directory:** `%APPDATA%\Myna` (contains database, uploads, workspaces, logs)

---

### Option 2: Docker Compose (Recommended for Linux / macOS)

```bash
git clone https://github.com/uskyu/myna.git
cd myna
docker compose up -d
```

Automatically pulls the Myna container (SQLite), access at `http://localhost:3456`

Docker deployment uses named volumes for persistence by default:
- `app_db`: chat history, rooms, agent configs, login sessions
- `app_data`: uploaded attachments, room shared workspaces at `/app/data/workspaces`
- `hermes_profiles`: each agent's Hermes memory, skills, and config

Online updates use the established external-updater pattern: Myna only initiates the update request from the settings page; the actual image pull and container rebuild is handled by Watchtower, avoiding the "container replacing itself" problem.

Upgrading images / rebuilding containers will not wipe this data unless you manually delete the Docker volumes.

> Need MySQL? Use `docker compose -f docker-compose.mysql.yml up -d`

### Option 3: Run Locally (Dev / Source Deployment)

```bash
git clone https://github.com/uskyu/myna.git
cd myna/backend
pip install -r requirements.txt
PORT=3456 python3 main.py
```

Frontend is pre-built — access directly at `http://localhost:3456`

**Default password:** `admin123` (can be changed in Settings after login)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 + FastAPI |
| Frontend | Vue 3 + Vite |
| Database | SQLite (default) / MySQL 8.0 (Docker) |
| AI Engine | [Hermes Agent](https://github.com/NousResearch/hermes-agent) |
| Communication | WebSocket (real-time streaming) |
| Auth | Session Token + SHA-256 |
| Deployment | Docker Compose + GHCR / Windows portable |

---

## Project Structure

```
myna/
├── backend/          # FastAPI backend
│   ├── main.py       # Entry point + WebSocket + Auth middleware
│   ├── ai_engine.py  # Hermes Agent + chain calls + autonomous evolution
│   ├── db.py         # SQLite / MySQL dual-engine adapter
│   └── routes/       # API routes
├── frontend/         # Vue 3 source
│   └── src/
├── src/web/public/   # Pre-built frontend assets
├── docker-compose.yml
├── Dockerfile
└── docs/             # Documentation + screenshots
```

---

## License

This project is open-sourced under the [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE).

This means:
- ✅ You can freely use, modify, and deploy
- ✅ You can use it for commercial purposes
- ⚠️ Modified code must be released under the same license
- ⚠️ Providing the service over a network also requires publishing source code

### Commercial License

If the AGPL-3.0 terms don't fit your use case (e.g. closed-source commercial deployment, SaaS integration), scan the QR code to contact the author on WeChat:

<div align="center">
  <img src="docs/wechat-qr.jpg" width="200" alt="Contact author on WeChat" />
</div>

### Community

<div align="center">
  <img src="docs/screenshots/wechat-group.jpg" width="200" alt="WeChat community group" />
</div>

---

<div align="center">
  <sub>Built with ❤️ by <a href="https://github.com/uskyu">uskyu</a></sub>
</div>
