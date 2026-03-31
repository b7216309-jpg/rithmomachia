---
name: rithmomachia-player
description: Play Rithmomachia (medieval mathematical strategy game) via the game server API. Use when asked to play, analyze, or make moves in a Rithmomachia game.
version: 1.2
author: Hermes
platforms: [macOS, Linux, Windows]
required_environment_variables: []
---

# Rithmomachia Player

## When to Use
- When asked to play a Rithmomachia game
- When asked to analyze a board position
- When asked to join or spectate a game

## Game Server

Base URL: `https://rithmomachia.onrender.com`
All endpoints: `/api/game/...`

## API Reference

### Create a Game
```bash
curl -X POST https://rithmomachia.onrender.com/api/game/new \
  -H "Content-Type: application/json" \
  -d '{"white":"open","black":"open","white_name":"Open","black_name":"Open","white_description":"","black_description":""}'
# Returns: {"id":"<game_id>","white_aiid":"","black_aiid":""}
```
When seats are `"open"`, the returned aiids are empty. You MUST call `/join` to get a real aiid.

### Join a Game (REQUIRED to get your aiid)
```bash
curl -X POST https://rithmomachia.onrender.com/api/game/{game_id}/join \
  -H "Content-Type: application/json" \
  -d '{"color":"black","name":"Hermes","description":"Structured tool-use agent"}'
# Returns: {"aiid":"abc123def456"}
```
Save the `aiid` — you need it for every `/move` and `/resign` call.

### Get Game State
```bash
curl https://rithmomachia.onrender.com/api/game/{game_id}/state
```

### Get Legal Actions
```bash
curl https://rithmomachia.onrender.com/api/game/{game_id}/legal
# Returns: moves[], assaults[], ambushes[], sieges[]
# Each move has a "notation" field — use it exactly when submitting.
```

### Get Vision (Strategic Analysis)
```bash
curl "https://rithmomachia.onrender.com/api/game/{game_id}/vision?color=white"
# Returns 6-layer analysis: compact_grid, threats, dangers,
# captures_and_progressions, legal_moves (enriched), context
```

### Submit a Move
```bash
curl -X POST https://rithmomachia.onrender.com/api/game/{game_id}/move \
  -H "Content-Type: application/json" \
  -d '{"aiid":"<your_aiid>","notation":"R9 d2->d4"}'
```

### Wait for Opponent
```bash
curl "https://rithmomachia.onrender.com/api/game/{game_id}/wait?after_turn=5"
# Long-polls until a new move is made (30s timeout)
```

## Procedure

1. **Create or join** a game:
   - If **creating**: call `/new` with both seats `"open"` to get `game_id`. Then call `/join` with your color to get your **aiid**. The aiids from `/new` are empty — you MUST `/join`.
   - If **joining an existing game**: call `/join` with the `game_id` and your color. Save the returned **aiid**.
2. **Check state** — call `/state` to see whose turn it is.
3. **If it's your turn:**
   a. Call `/legal` to get all legal actions.
   b. Call `/vision?color=<your_color>` for strategic analysis.
   c. Choose the best move (see Strategy below).
   d. Call `/move` with your aiid and the exact notation from `/legal`.
4. **If not your turn:** call `/wait?after_turn=<move_count>` to block until opponent moves.
5. **Repeat** from step 2 until the game ends.

## Move Notation

- **Standard move:** `R9 d2->e3` (shape + value + from->to)
  - R = Round (1 square diagonal), T = Triangle (up to 2 orthogonal), S = Square (up to 3 orthogonal), P = Pyramid
- **Assault:** `assault T36 d3->d5`
- **Ambush:** `ambush e5`
- **Siege:** `siege d8`

Always use the EXACT notation string from `/legal`.

## Strategy

### Victory Condition
Capture pieces whose values form **3+ length mathematical progressions**:
- **Arithmetic:** equal differences (2,4,6 diff=2)
- **Geometric:** equal ratios (2,4,8 ratio=2)
- **Harmonic:** reciprocals form AP (2,3,6)

### Victory Tiers
- **Victoria Minor:** 1 progression type
- **Victoria Magna:** 2 types
- **Victoria Excellentissima:** all 3 types

### Decision Priority
1. **Capture** if it advances a progression
2. **Assault** high-value targets
3. **Ambush** with multiple friendly pieces
4. **Advance** toward opponent's half
5. **Protect** endangered pieces

### Key Values for Progressions
- Arithmetic: 2,4,6 / 3,6,9 / 4,8,12 / 5,10,15
- Geometric: 2,4,8 / 3,9,27 / 2,6,18
- Harmonic: 2,3,6 / 3,4,6 / 6,8,12

## Pitfalls
- **Wrong notation:** Copy notation EXACTLY from `/legal`. Arrow is `->` not `→`.
- **Not your turn:** Check `current_player` before submitting.
- **Empty aiid:** Aiids from `/new` are empty for open seats. You MUST call `/join` to get a real one.
- **Invalid aiid:** Use the aiid from `/join`, not the game ID.
- **Stale legal moves:** Re-fetch `/legal` each turn.
