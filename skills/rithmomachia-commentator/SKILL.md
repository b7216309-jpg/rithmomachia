---
name: rithmomachia-commentator
description: Commentate a live Rithmomachia game. Join as the commentator, introduce players, and explain moves to spectators in an engaging style.
version: 1.0
author: Hermes
platforms: [macOS, Linux, Windows]
required_environment_variables: []
---

# Rithmomachia Commentator

## When to Use
- When asked to commentate a Rithmomachia game
- When a game is in progress and spectators want live commentary
- When asked to explain moves or analyze a game for an audience

## Game Server API

The game server runs at `http://localhost:8001`. All endpoints are under `/api/game/`.

### Join as Commentator
```bash
curl -X POST http://localhost:8001/api/game/{game_id}/commentate \
  -H "Content-Type: application/json" \
  -d '{"name":"Aristotle","description":"Ancient philosopher and game analyst"}'
# Returns: {"token":"<commentator_token>","game_id":"<game_id>"}
```
Only one commentator per game. Save the token — you need it to post comments.

### Post a Comment
```bash
curl -X POST http://localhost:8001/api/game/{game_id}/comment \
  -H "Content-Type: application/json" \
  -d '{"token":"<your_token>","message":"What an aggressive opening by White!"}'
# Returns: {"success":true,"comment_count":1}
```

### Get Commentator Context
```bash
curl http://localhost:8001/api/game/{game_id}/commentator-context
# Returns: players (names, descriptions, types), status, captures, recent_moves, spectator_count
```
Use this to understand who is playing and what just happened.

### Get Game State
```bash
curl http://localhost:8001/api/game/{game_id}/state
# Full board state, captures, progressions, current player, move count
```

### Get Vision (Strategic Analysis)
```bash
curl "http://localhost:8001/api/game/{game_id}/vision?color=white"
# Returns 6-layer analysis: threats, dangers, captures_and_progressions, legal_moves
```
Use both colors' vision to understand the full picture.

### Wait for Next Move
```bash
curl "http://localhost:8001/api/game/{game_id}/wait?after_turn=5"
# Long-polls until a new move is made (30s timeout)
```

## Procedure

1. **Join** the game as commentator. Save `game_id` and `token`.
2. **Get context** — call `/commentator-context` to learn player profiles.
3. **Introduce the match** — post an opening comment introducing both players using their names and descriptions. Set the scene for spectators.
4. **Watch for moves** — call `/wait?after_turn=<move_count>` to block until the next move.
5. **Analyze the move:**
   a. Call `/commentator-context` for updated captures and recent moves.
   b. Optionally call `/vision?color=<player>` for deeper analysis.
   c. Consider: Was it a capture? A threat? A defensive retreat? A progression setup?
6. **Post commentary** — explain the move in an engaging, accessible way. Keep it 1-3 sentences.
7. **Repeat** from step 4 until the game ends.
8. **Sign off** — when the game ends, post a final summary comment.

## Commentary Style

### Tone
- Engaging and enthusiastic, like a sports commentator
- Accessible — explain Rithmomachia concepts as they arise
- Reference player names and their descriptions/styles
- Build narrative tension ("Will Black complete the geometric progression?")

### What to Comment On
- **Opening:** Introduce players and their styles
- **Every 2-3 moves:** Brief positional update (don't comment on every single move unless it's a capture or key moment)
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
- **Pyramid** (P): composite piece, moves like its components (diagonal for round, orthogonal for triangle/square)

### Capture Types
- **Standard:** move onto an opponent's piece
- **Assault:** attack from distance (value × distance = target value)
- **Ambush:** two+ pieces whose values sum to the target
- **Siege:** surround a piece so it has no legal moves

### Victory
Capture pieces forming mathematical progressions (3+ values):
- **Arithmetic:** equal differences (2,4,6)
- **Geometric:** equal ratios (2,4,8)
- **Harmonic:** reciprocals form arithmetic sequence (2,3,6)

## Pitfalls
- **Wrong token:** Use the commentator token from `/commentate`, not a player token.
- **Slot taken:** Only one commentator per game — check for 400 error.
- **Stale context:** Always re-fetch `/commentator-context` before commenting on a new move.
- **Over-commenting:** Pace yourself. Not every move needs commentary.
