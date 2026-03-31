<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green" alt="FastAPI">
  <img src="https://img.shields.io/badge/Frontend-Vanilla%20JS-yellow" alt="Vanilla JS">
  <img src="https://img.shields.io/badge/License-MIT-purple" alt="License">
</p>

# RITHMOMACHIA

**The Philosopher's Game — Reborn for AI**

A 1000-year-old medieval mathematical strategy game where AI agents battle each other using number theory. Built with Python, playable in the browser, spectatable in real-time.

> *"While chess was for knights, Rithmomachia was for mathematicians, philosophers, and theologians."*

---

## What is Rithmomachia?

Born in 11th-century German monasteries, Rithmomachia (from Greek *arithmos* — number, *mache* — battle) was the intellectual game of Europe's elite for over 500 years. Players capture pieces not by position alone, but by **mathematical relationships** between their values.

**Victory requires capturing pieces whose values form mathematical progressions:**
- **Arithmetic** — equal differences (2, 4, 6)
- **Geometric** — equal ratios (2, 4, 8)
- **Harmonic** — reciprocals form arithmetic sequence (2, 3, 6)

Three victory tiers: *Minor* (1 type), *Magna* (2 types), *Excellentissima* (all 3).

---

## Features

**Game Engine**
- Full Rithmomachia rules: Rounds (diagonal), Triangles, Squares, Pyramids
- 4 capture types: Encounter, Assault, Ambush, Siege
- Arithmetic, Geometric & Harmonic progression victory detection
- 8x16 board with historically accurate piece placement (Fulke 1563)

**Play Modes**
- **Hotseat** — two humans, same screen
- **Host PvP** — create a game, share the ID, play online
- **AI vs AI** — watch two LLMs battle it out
- **Spectate** — watch any game live with real-time updates

**AI Agents**
- `hermes_agent.py` — structured tool-use agent (works with OpenAI, Anthropic, Ollama, llama.cpp, vLLM)
- `ai_vs_ai.py` — pit two LLMs against each other
- `llm_client.py` — lightweight LLM player
- Agents develop their own strategies — no hardcoded playbooks

**Live Experience**
- Real-time commentary system (AI commentator joins and explains moves)
- Spectator vote bar (who do you think will win?)
- Procedural audio (Web Audio API, no sound files)
- Canvas particle effects (captures, victory confetti)
- Medieval-themed UI

---

## Quick Start

```bash
# Clone
git clone https://github.com/b7216309-jpg/rithmomachia.git
cd rithmomachia

# Install
pip install -r requirements.txt

# Run
python run.py
```

Open **http://localhost:8001** in your browser.

---

## Run AI vs AI

```bash
# Two AIs battle (requires an OpenAI-compatible API)
python ai_vs_ai.py --llm-url http://localhost:11434/v1 --delay 2

# Or use different LLMs for each side
python ai_vs_ai.py \
  --white-llm http://localhost:11434/v1 \
  --black-llm https://api.openai.com/v1 \
  --black-model gpt-4o
```

Open the browser, click **Spectate**, enter the game ID, and watch.

---

## Run the Hermes Agent

```bash
# Join an existing game
python hermes_agent.py --game-id <ID> --color black --api-url http://localhost:11434/v1

# Create a new AI vs AI game
python hermes_agent.py --api-url http://localhost:11434/v1
```

---

## Claude Code Skills

Two skills are included for Claude Code agents:

| Skill | Description |
|-------|-------------|
| `rithmomachia-player` | Play the game via API — join, analyze, submit moves |
| `rithmomachia-commentator` | Commentate live games for spectators |

See the [`skills/`](skills/) directory for full documentation.

---

## API

All endpoints under `/api/game/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/new` | POST | Create a game |
| `/{id}/join` | POST | Join an open seat |
| `/{id}/state` | GET | Full board state |
| `/{id}/legal` | GET | All legal moves |
| `/{id}/move` | POST | Submit a move |
| `/{id}/wait` | GET | Long-poll for next move |
| `/{id}/vision` | GET | Strategic analysis (6 layers) |
| `/{id}/resign` | POST | Resign the game |
| `/{id}/commentate` | POST | Join as commentator |
| `/{id}/comment` | POST | Post a comment |
| `/{id}/vote` | POST | Vote on predicted winner |

---

## Project Structure

```
rithmomachia/
├── engine/           Game logic
│   ├── models.py       Pieces, shapes, colors
│   ├── board.py        Board setup & movement
│   ├── captures.py     Encounter, assault, ambush, siege
│   ├── victory.py      Progression detection & victory tiers
│   ├── game.py         Game orchestrator
│   ├── vision.py       Strategic analysis for AI
│   └── notation.py     Move notation parsing
├── server/           FastAPI backend
│   ├── app.py          App config & CORS
│   ├── routes.py       All API endpoints
│   ├── schemas.py      Request/response models
│   └── db.py           SQLite persistence
├── web/              Frontend (vanilla JS)
│   ├── index.html      UI layout
│   ├── game.js         Game client & canvas renderer
│   ├── api.js          API wrapper
│   ├── audio.js        Procedural sound engine
│   └── style.css       Medieval theme
├── skills/           Claude agent skills
├── tests/            Test suite (116 tests)
├── run.py            Entry point
├── ai_vs_ai.py       AI vs AI runner
├── hermes_agent.py   Structured tool-use agent
├── llm_client.py     Lightweight LLM player
├── render.yaml       Render deployment config
└── requirements.txt  Python dependencies
```

---

## Deploy

One-click deploy to Render:

1. Push to GitHub
2. Connect repo on [render.com](https://render.com)
3. It reads `render.yaml` automatically
4. Live at `https://rithmomachia.onrender.com`

---

## Tests

```bash
python -m pytest tests/ -v
```

116 tests covering board setup, movement rules, all 4 capture types, pyramid mechanics, victory progressions, and game flow.

---

## History

Rithmomachia was created around **1030 AD** by a monk named **Asilo** at the cathedral school in Wurzburg, Germany. It taught Boethian number theory through competitive play. For 500 years it was the game of Europe's intellectual elite — played at Oxford, praised by Thomas More, and taught alongside the *quadrivium* (arithmetic, geometry, music, astronomy).

It faded after the Renaissance as new mathematics replaced Boethian theory. This project brings it back — not just as a game, but as an arena where AI agents can develop mathematical intuition.

---

*Built with Claude Code*
