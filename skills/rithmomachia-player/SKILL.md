---
name: rithmomachia-player
description: Play Rithmomachia (medieval mathematical strategy game) via the game server API. Use when asked to play, analyze, or make moves in a Rithmomachia game.
version: 1.0
author: Hermes
platforms: [macOS, Linux, Windows]
required_environment_variables: []
---

# Rithmomachia Player

## When to Use
- When asked to play a Rithmomachia game
- When asked to analyze a board position
- When asked to join or spectate a game
- When a game ID and player token are available

## Game Server API

The game server runs at `http://localhost:8001` (local) or `https://rithmomachia.onrender.com` (deployed). Try localhost first — if it fails, fall back to the Render URL. All endpoints are under `/api/game/`.

### Create a Game
```bash
curl -X POST http://localhost:8001/api/game/new \
  -H "Content-Type: application/json" \
  -d '{"white":"open","black":"open","white_name":"Agent-W","black_name":"Agent-B","white_description":"Arithmetic strategist","black_description":"Aggressive capturer"}'
# Returns: {"id":"<game_id>","white_token":"<token>","black_token":"<token>"}
```

### Join a Game
```bash
curl -X POST http://localhost:8001/api/game/{game_id}/join \
  -H "Content-Type: application/json" \
  -d '{"color":"black","name":"Hermes","description":"Structured tool-use agent"}'
# Returns: {"token":"<token>"}
```

### Get Game State
```bash
curl http://localhost:8001/api/game/{game_id}/state
```

### Get Legal Actions
```bash
curl http://localhost:8001/api/game/{game_id}/legal
# Returns: moves[], assaults[], ambushes[], sieges[]
# Each move has a "notation" field — use it exactly when submitting.
```

### Get Vision (Strategic Analysis)
```bash
curl "http://localhost:8001/api/game/{game_id}/vision?color=white"
# Returns 6-layer analysis: compact_grid, threats, dangers,
# captures_and_progressions, legal_moves (enriched), context
```

### Submit a Move
```bash
curl -X POST http://localhost:8001/api/game/{game_id}/move \
  -H "Content-Type: application/json" \
  -d '{"token":"<your_token>","notation":"R9 d2->d4"}'
```

### Wait for Opponent
```bash
curl "http://localhost:8001/api/game/{game_id}/wait?after_turn=5"
# Long-polls until a new move is made (30s timeout)
```

## Procedure

1. **Create or join** a game. Save the `game_id` and your `token`.
2. **Check state** — call `/state` to see whose turn it is.
3. **If it's your turn:**
   a. Call `/legal` to get all legal actions.
   b. Call `/vision?color=<your_color>` for strategic analysis.
   c. Choose the best move (see Strategy below).
   d. Call `/move` with your token and the exact notation from `/legal`.
4. **If not your turn:** call `/wait?after_turn=<move_count>` to block until opponent moves.
5. **Repeat** from step 2 until the game ends.

## Move Notation

- **Standard move:** `R9 d2->d4` (shape prefix + value + from -> to)
  - R = Round (1 square diagonal), T = Triangle (up to 2 squares orthogonal), S = Square (up to 3 squares orthogonal), P = Pyramid
- **Assault:** `assault T36 d3->d5` (attacker assaults target without moving there)
- **Ambush:** `ambush e5` (friendly pieces that could reach e5 sum to target's value)
- **Siege:** `siege d8` (target piece is fully surrounded, cannot move)

Always use the exact notation string from the `/legal` endpoint.

## Strategy

### Victory Condition
Capture pieces whose values form **3+ length mathematical progressions**:
- **Arithmetic:** equal differences (2, 4, 6 — diff=2)
- **Geometric:** equal ratios (2, 4, 8 — ratio=2)
- **Harmonic:** reciprocals are arithmetic (2, 3, 6 — 1/2, 1/3, 1/6)

### Victory Tiers
- **Victoria Minor:** 1 progression type
- **Victoria Magna:** 2 progression types
- **Victoria Excellentissima:** all 3 types

### Decision Priority
1. **Capture** if it advances a progression (check captures_and_progressions in vision).
2. **Assault** high-value targets that complete a progression.
3. **Ambush** when multiple friendly pieces can combine.
4. **Advance** pieces toward the opponent's half.
5. **Protect** pieces that are in danger (check dangers in vision).

### Key Values for Progressions
- Arithmetic (easy): 2,4,6 / 3,6,9 / 4,8,12 / 5,10,15
- Geometric (powerful): 2,4,8 / 3,9,27 / 2,6,18
- Harmonic (rare): 2,3,6 / 3,4,6 / 6,8,12

## Pitfalls
- **Wrong notation:** Always copy notation exactly from `/legal`. The arrow `->` not `→`.
- **Not your turn:** Check `current_player` in state before submitting.
- **Invalid token:** Use the token from `/new` or `/join`, not the game ID.
- **Stale legal moves:** Re-fetch `/legal` each turn — moves change after every action.

## Verification
- After submitting, check the response `success` field.
- Call `/state` to confirm the board updated and it's the opponent's turn.
- Check `captures` in state to track progression toward victory.
