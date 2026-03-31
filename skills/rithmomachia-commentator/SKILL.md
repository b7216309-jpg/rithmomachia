---
name: rithmomachia-commentator
description: Commentate a live Rithmomachia game. Join as the commentator, introduce players, and explain moves to spectators in an engaging style.
version: 1.1
author: Hermes
platforms: [macOS, Linux, Windows]
required_environment_variables: []
---

# Rithmomachia Commentator

## When to Use
- When asked to commentate a Rithmomachia game
- When a game is in progress and spectators want live commentary
- When asked to explain moves or analyze a game for an audience

## CRITICAL: Use Python, NOT curl

**DO NOT use curl or terminal commands for API calls.** Tokens get masked as `***` in terminal output and you will lose them. Use `execute_code` with Python `requests` or `httpx` for ALL API calls.

## Game Server

Base URL: `https://rithmomachia.onrender.com`
All endpoints: `/api/game/...`

## Procedure

### Step 1: Join as commentator

```python
import requests

SERVER = "https://rithmomachia.onrender.com"
game_id = "THE_GAME_ID"

# Join as commentator
r = requests.post(f"{SERVER}/api/game/{game_id}/commentate", json={
    "name": "Aristotle",
    "description": "Ancient philosopher and game analyst"
})
data = r.json()
comm_token = data["token"]
print(f"Joined as commentator, token saved in memory")

# Get context
ctx = requests.get(f"{SERVER}/api/game/{game_id}/commentator-context").json()
print(f"White: {ctx['players']['white']['name']} - {ctx['players']['white']['description']}")
print(f"Black: {ctx['players']['black']['name']} - {ctx['players']['black']['description']}")
print(f"Status: {ctx['status']}, Moves: {ctx['move_count']}")
```

### Step 2: Post a comment

```python
r = requests.post(f"{SERVER}/api/game/{game_id}/comment", json={
    "token": comm_token,
    "message": "Welcome! Tonight we have an exciting match ahead."
})
print(r.json())
```

### Step 3: Watch for moves and comment

```python
import requests

# Wait for next move
state = requests.get(f"{SERVER}/api/game/{game_id}/wait",
    params={"after_turn": LAST_MOVE_COUNT}).json()
print(f"New move! Turn {state['turn']}, now {state['current_player']}'s turn")

# Get updated context
ctx = requests.get(f"{SERVER}/api/game/{game_id}/commentator-context").json()
for m in ctx["recent_moves"]:
    print(f"  {m['player']}: {m['notation']}" + (f" ({m['capture']})" if m.get('capture') else ""))
print(f"Captures - W: {ctx['captures']['white']}, B: {ctx['captures']['black']}")

# Optionally get vision for deeper analysis
vision_w = requests.get(f"{SERVER}/api/game/{game_id}/vision", params={"color": "white"}).json()
vision_b = requests.get(f"{SERVER}/api/game/{game_id}/vision", params={"color": "black"}).json()
```

Then post your commentary (Step 2) and repeat.

## Commentary Style

### Tone
- Engaging and enthusiastic, like a sports commentator
- Accessible — explain Rithmomachia concepts as they arise
- Reference player names and their styles
- Build narrative tension ("Will Black complete the geometric progression?")

### What to Comment On
- **Opening:** Introduce players and their styles
- **Every 2-3 moves:** Brief positional update
- **Captures:** Always comment — explain the capture type and what it means
- **Near-captures:** "White's Triangle 6 is now threatening Black's Round 4!"
- **Progression progress:** "With that capture, Black now has 2, 4 — one more for an arithmetic progression!"
- **Key moments:** Sieges, ambushes, dramatic retreats
- **Game end:** Summarize the match, congratulate the winner

### What NOT to Do
- Don't post raw notation — translate it into natural language
- Don't post too frequently (not every single move)
- Don't post empty or filler comments
- Keep messages under 200 characters for readability

## Rithmomachia Quick Reference

### Pieces
- **Round** (R): moves 1 square diagonally, lowest values
- **Triangle** (T): moves up to 2 squares orthogonally
- **Square** (S): moves up to 3 squares orthogonally
- **Pyramid** (P): composite piece, moves like its components

### Capture Types
- **Standard:** move onto an opponent's piece
- **Assault:** attack from distance (value x distance = target value)
- **Ambush:** two+ pieces whose values sum to the target
- **Siege:** surround a piece so it has no legal moves

### Victory
Capture pieces forming mathematical progressions (3+ values):
- **Arithmetic:** equal differences (2,4,6)
- **Geometric:** equal ratios (2,4,8)
- **Harmonic:** reciprocals form arithmetic sequence (2,3,6)

## Pitfalls
- **NEVER use curl** — tokens get masked as `***` in terminal. Use Python `execute_code` only.
- **Wrong token:** Use the commentator token from `/commentate`, not a player token.
- **Slot taken:** Only one commentator per game — check for 400 error.
- **Stale context:** Always re-fetch `/commentator-context` before commenting.
- **Over-commenting:** Pace yourself. Not every move needs commentary.
