"""AI vs AI client for Rithmomachia.

Creates a game and plays both sides using LLM(s). The web UI can spectate
in real-time by opening the game URL.

Usage:
    # Start the game server first:
    python run.py

    # Run two AIs against each other (same LLM):
    python ai_vs_ai.py --llm-url http://localhost:8080/v1/chat/completions

    # Two different LLMs:
    python ai_vs_ai.py \
        --white-llm http://localhost:8080/v1/chat/completions \
        --black-llm http://localhost:11434/v1/chat/completions \
        --black-model llama3

    # With delay between moves for spectating:
    python ai_vs_ai.py --delay 2.0 --llm-url http://localhost:8080/v1/chat/completions
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx

from llm_client import (
    create_game, get_state, get_vision, submit_move, ask_llm,
    extract_notation, SYSTEM_PROMPT, DEFAULT_SERVER, DEFAULT_LLM,
)


WHITE_PERSONA = """You are WHITE in Rithmomachia, a medieval mathematical strategy game.
You play methodically, favoring arithmetic progressions and positional control.
Advance your pieces to control the center, and look for encounter and assault captures.

IMPORTANT: Respond with ONLY the move notation, exactly as shown in the legal moves list.
No explanation, no commentary. Just the move.
"""

BLACK_PERSONA = """You are BLACK in Rithmomachia, a medieval mathematical strategy game.
You play aggressively, seeking geometric and harmonic progressions.
Prioritize captures that advance your progression goals, even at positional cost.

IMPORTANT: Respond with ONLY the move notation, exactly as shown in the legal moves list.
No explanation, no commentary. Just the move.
"""


def play_ai_vs_ai(server: str,
                  white_llm: str, white_model: str, white_temp: float,
                  black_llm: str, black_model: str, black_temp: float,
                  delay: float, max_turns: int):
    """Run an AI vs AI game."""

    # Create game with both seats open
    resp = create_game(server, "open", "open")
    game_id = resp["id"]
    white_token = resp["white_token"]
    black_token = resp["black_token"]

    print(f"\n{'='*55}")
    print(f"  Rithmomachia — AI vs AI")
    print(f"  Game ID: {game_id}")
    print(f"  Server:  {server}")
    print(f"  White LLM: {white_llm}" + (f" ({white_model})" if white_model else ""))
    print(f"  Black LLM: {black_llm}" + (f" ({black_model})" if black_model else ""))
    print(f"  Spectate: open {server} in browser, click 'Spectate'")
    print(f"{'='*55}\n")

    players = {
        "white": {
            "token": white_token,
            "llm_url": white_llm,
            "model": white_model,
            "temp": white_temp,
            "persona": WHITE_PERSONA,
            "name": "White",
        },
        "black": {
            "token": black_token,
            "llm_url": black_llm,
            "model": black_model,
            "temp": black_temp,
            "persona": BLACK_PERSONA,
            "name": "Black",
        },
    }

    turn_count = 0

    while turn_count < max_turns:
        state = get_state(server, game_id)

        if state["status"] != "active":
            print(f"\n{'='*55}")
            print(f"  GAME OVER: {state['status']}")
            print(f"  Turns played: {state['move_count']}")
            w_caps = state["captures"]["white"]
            b_caps = state["captures"]["black"]
            print(f"  White captures: {w_caps}")
            print(f"  Black captures: {b_caps}")
            print(f"{'='*55}")
            break

        current = state["current_player"]
        player = players[current]
        turn_count += 1

        print(f"--- Turn {state['turn']} ({player['name']}) ---")

        # Get vision for current player
        vision = get_vision(server, game_id, current)
        legal_notations = [m["notation"] for m in vision["legal_moves"]]

        if not legal_notations:
            print(f"  No legal moves! This shouldn't happen.")
            break

        # Show available info
        threats = vision["threats"]
        if threats:
            print(f"  Captures available: {len(threats)}")
            for t in threats[:3]:
                print(f"    {t['capture']}: {t['target']} [{t['math']}]")

        # Ask LLM
        max_retries = 3
        move_made = False
        reasoning = ""

        for attempt in range(max_retries):
            try:
                # Use player's persona instead of generic system prompt
                raw = ask_llm_with_persona(
                    player["llm_url"], player["model"],
                    player["persona"], vision["raw_text"],
                    player["temp"],
                )
                reasoning = raw
                print(f"  LLM: {raw[:80]}{'...' if len(raw) > 80 else ''}")

                notation = extract_notation(raw, legal_notations)
                if notation is None:
                    print(f"  No match (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        continue
                    notation = legal_notations[0]
                    print(f"  Fallback: {notation}")

                result = submit_move(server, game_id, player["token"], notation)
                if result["success"]:
                    print(f"  Played: {notation}")
                    if result["captures"]:
                        for cap in result["captures"]:
                            print(f"  CAPTURE! {cap['description']}")
                    if result.get("victory"):
                        progs = result["victory"]
                        print(f"\n  VICTORY for {player['name']}!")
                        for p in progs:
                            print(f"    {p['type']}: {p['values']}")
                    move_made = True
                    break
                else:
                    print(f"  Rejected: {result['error']} (attempt {attempt + 1})")

            except httpx.ConnectError:
                print(f"  LLM connection failed. Is the LLM server running at {player['llm_url']}?")
                return
            except Exception as e:
                print(f"  Error: {e} (attempt {attempt + 1})")

        if not move_made:
            notation = legal_notations[0]
            print(f"  All retries failed. Forcing: {notation}")
            submit_move(server, game_id, player["token"], notation)

        if delay > 0:
            time.sleep(delay)

    else:
        print(f"\nMax turns ({max_turns}) reached.")

    print("\nGame complete.")


def ask_llm_with_persona(llm_url: str, model: str, persona: str,
                         vision_text: str, temperature: float) -> str:
    """Send vision to LLM with a specific persona system prompt."""
    payload = {
        "messages": [
            {"role": "system", "content": persona},
            {"role": "user", "content": vision_text},
        ],
        "temperature": temperature,
        "max_tokens": 50,
    }
    if model:
        payload["model"] = model

    r = httpx.post(llm_url, json=payload, timeout=120.0)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()


def main():
    parser = argparse.ArgumentParser(description="Rithmomachia AI vs AI")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--llm-url", default=DEFAULT_LLM,
                        help="LLM endpoint for both players (overridden by --white-llm/--black-llm)")
    parser.add_argument("--white-llm", help="LLM endpoint for white")
    parser.add_argument("--black-llm", help="LLM endpoint for black")
    parser.add_argument("--model", default="", help="Model for both players")
    parser.add_argument("--white-model", help="Model for white")
    parser.add_argument("--black-model", help="Model for black")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--white-temp", type=float, default=None)
    parser.add_argument("--black-temp", type=float, default=None)
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Seconds between moves (for spectating)")
    parser.add_argument("--max-turns", type=int, default=200)
    args = parser.parse_args()

    white_llm = args.white_llm or args.llm_url
    black_llm = args.black_llm or args.llm_url
    white_model = args.white_model or args.model
    black_model = args.black_model or args.model
    white_temp = args.white_temp if args.white_temp is not None else args.temperature
    black_temp = args.black_temp if args.black_temp is not None else args.temperature

    play_ai_vs_ai(
        args.server,
        white_llm, white_model, white_temp,
        black_llm, black_model, black_temp,
        args.delay, args.max_turns,
    )


if __name__ == "__main__":
    main()
