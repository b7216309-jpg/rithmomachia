---
name: rithmomachia-player
description: Play Rithmomachia (medieval mathematical strategy game) via the game server API. Use when asked to play, analyze, or make moves in a Rithmomachia game.
version: 1.1
author: Hermes
platforms: [macOS, Linux, Windows]
required_environment_variables: []
---

# Rithmomachia Player

## When to Use
- When asked to play a Rithmomachia game
- When asked to analyze a board position
- When asked to join or spectate a game

## CRITICAL: Use Python, NOT curl

**DO NOT use curl or terminal commands for API calls.** Tokens get masked as `***` in terminal output and you will lose them forever. Use `execute_code` with Python `requests` or `httpx` for ALL API calls. This keeps tokens in memory where you can actually use them.

## Game Server

Base URL: `https://rithmomachia.onrender.com`
All endpoints: `/api/game/...`

## Procedure

### Step 1: Create or Join a game

Use a SINGLE `execute_code` block to create AND join in one shot. Store the token in a variable.

```python
import requests

SERVER = "https://rithmomachia.onrender.com"

# Create a new game (both seats open)
r = requests.post(f"{SERVER}/api/game/new", json={
    "white": "open", "black": "open",
    "white_name": "Open", "black_name": "Open",
    "white_description": "", "black_description": ""
})
game_id = r.json()["id"]
print(f"Game created: {game_id}")

# IMMEDIATELY join your seat to get a real token
my_color = "black"  # or "white"
r2 = requests.post(f"{SERVER}/api/game/{game_id}/join", json={
    "color": my_color,
    "name": "YourName",
    "description": "Your description"
})
my_token = r2.json()["token"]
print(f"Joined as {my_color}, token saved in memory")
print(f"Game ID: {game_id}")
```

To join an EXISTING game:
```python
import requests
SERVER = "https://rithmomachia.onrender.com"
game_id = "THE_GAME_ID"
my_color = "black"  # pick the open seat

r = requests.post(f"{SERVER}/api/game/{game_id}/join", json={
    "color": my_color,
    "name": "YourName",
    "description": "Your description"
})
my_token = r.json()["token"]
print(f"Joined as {my_color}, token saved")
```

### Step 2: Game loop

Run this in `execute_code` each turn. Keep `game_id`, `my_token`, `my_color`, and `SERVER` from step 1.

```python
import requests, time

# Check state
state = requests.get(f"{SERVER}/api/game/{game_id}/state").json()
print(f"Turn {state['turn']}, current: {state['current_player']}, status: {state['status']}")

if state["current_player"] != my_color:
    # Wait for opponent
    print("Waiting for opponent...")
    state = requests.get(f"{SERVER}/api/game/{game_id}/wait", params={"after_turn": state["move_count"]}).json()
    print(f"Opponent moved! Now turn {state['turn']}")

# Get legal moves
legal = requests.get(f"{SERVER}/api/game/{game_id}/legal").json()
moves = legal["moves"]
assaults = legal.get("assaults", [])
ambushes = legal.get("ambushes", [])
sieges = legal.get("sieges", [])
print(f"Legal: {len(moves)} moves, {len(assaults)} assaults, {len(ambushes)} ambushes, {len(sieges)} sieges")

# Get vision for strategy
vision = requests.get(f"{SERVER}/api/game/{game_id}/vision", params={"color": my_color}).json()
print(f"Threats: {len(vision.get('threats', []))}, Dangers: {len(vision.get('dangers', []))}")

# Show capture moves and top regular moves
for m in moves:
    if m.get("is_capture"):
        print(f"  CAPTURE: {m['notation']}")
for a in assaults:
    print(f"  ASSAULT: {a['description']}")
for a in ambushes:
    print(f"  AMBUSH: {a['description']}")

# Show first 10 moves
for m in moves[:10]:
    print(f"  {m['notation']} ({m['piece_label']} {m['from_pos']}->{m['to_pos']})")
```

### Step 3: Submit your move

```python
notation = "R9 d2->e3"  # EXACT notation from /legal

result = requests.post(f"{SERVER}/api/game/{game_id}/move", json={
    "token": my_token,
    "notation": notation
}).json()

if result["success"]:
    print(f"Move played: {result['notation']}")
    if result.get("captures"):
        for c in result["captures"]:
            print(f"  Captured: {c['description']}")
    if result.get("victory"):
        print(f"VICTORY! {result['victory_type']}")
else:
    print(f"Move failed: {result.get('error')}")
```

Then go back to Step 2 and repeat.

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
- **NEVER use curl** — tokens get masked as `***` in terminal. Use Python `execute_code` only.
- **Wrong notation:** Copy notation EXACTLY from `/legal`. Arrow is `->` not `→`.
- **Not your turn:** Check `current_player` before submitting.
- **Token lost?** You must re-join (if seat is still open) to get a new token. Tokens are only returned by `/join`.
- **Stale legal moves:** Re-fetch `/legal` each turn.
