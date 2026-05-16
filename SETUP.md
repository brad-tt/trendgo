# TrendGo Setup

This repository contains the shareable TrendGo source code and documentation. It intentionally does not include private trading data, local SQLite databases, generated frontend builds, or `node_modules`.

## Requirements

- Python 3.11+
- Node.js 20+
- npm

## Backend

```bash
cd app
python3 db_init.py
python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8526
```

The database is created locally at `app/database/toptrader.db`. It is ignored by Git.

## Frontend

```bash
cd app/frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually:

```text
http://127.0.0.1:5173/premarket
```

## Production Build

```bash
cd app/frontend
npm run build
```

Generated files under `app/frontend/dist/` are ignored.

## Agent Skill

The Codex Skill source is in `skills/trendgo.md`.

To install it locally as a Codex skill:

```bash
mkdir -p ~/.agents/skills/trendgo
cp skills/trendgo.md ~/.agents/skills/trendgo/SKILL.md
```

Then invoke it in Codex with:

```text
$trendgo 记一笔开仓：54927牛证，0.054入场，3手，止损0.044，A级，方向位置确认。
```

## Validation

```bash
cd app
python3 -m py_compile api_server.py local_web.py db_init.py database/dal.py core/*.py scripts/*.py
python3 scripts/replay_agent_commit_sandbox.py
python3 scripts/replay_agent_write_sandbox_suite.py
```

```bash
cd app/frontend
npm run build
```

