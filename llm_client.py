"""Example LLM client for Rithmomachia.

Connects to the game server + any OpenAI-compatible LLM endpoint.
Demonstrates the play loop: wait → vision → LLM call → move.

Usage:
    # Start the game server first:
    python run.py

    # Create a game with one open seat:
    curl -X POST http://localhost:8001/api/game/new \
        -H "Content-Type: application/json" \
        -d '{"white":"human","black":"open"}'

    # Run this client (it joins as black):
    python llm_client.py --game-id <id> --color black \
        --llm-url http://localhost:8080/v1/chat/completions

    # Or use Ollama:
    python llm_client.py --game-id <id> --color black \
        --llm-url http://localhost:11434/v1/chat/completions \
        --model llama3

    # Or create a new AI-vs-AI game:
    python llm_client.py --new-game --color white \
        --llm-url http://localhost:8080/v1/chat/completions
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time

import httpx


SYSTEM_PROMPT = """You are playing Rithmomachia, a medieval mathematical strategy game.
You will receive a board state with all legal moves listed. Your job is to choose the best move.

Strategy tips:
- Capture pieces whose values help you form arithmetic, geometric, or harmonic progressions
- Protect your pieces from opponent captures
- Prioritize captures that advance your progression toward victory
- Watch for assault opportunities (value × distance relationships)
- Be aware of siege threats (don't let your pieces get surrounded)

IMPORTANT: Respond with ONLY the move notation, exactly as shown in the legal moves list.
Do not add explanation, commentary, or any other text. Just the move notation.

Example valid responses:
  R9 d2->d4
  assault T36 d3->d5
  ambush e5
  siege d8
"""

DEFAULT_SERVER = "http://localhost:8001"
DEFAULT_LLM = "http://localhost:8080/v1/chat/completions"


def create_game(server: str, white: str, black: str) -> dict:
    """Create a new game on the server."""
    r = httpx.post(f"{server}/api/game/new", json={"white": white, "black": black})
    r.raise_for_status()
    return r.json()


def join_game(server: str, game_id: str, color: str, name: str) -> str:
    """Join an existing game. Returns the token."""
    r = httpx.post(
        f"{server}/api/game/{game_id}/join",
        json={"color": color, "name": name},
    )
    r.raise_for_status()
    return r.json()["token"]


def get_state(server: str, game_id: str) -> dict:
    r = httpx.get(f"{server}/api/game/{game_id}/state")
    r.raise_for_status()
    return r.json()


def get_vision(server: str, game_id: str, color: str) -> dict:
    r = httpx.get(f"{server}/api/game/{game_id}/vision", params={"color": color})
    r.raise_for_status()
    return r.json()


def submit_move(server: str, game_id: str, token: str, notation: str) -> dict:
    r = httpx.post(
        f"{server}/api/game/{game_id}/move",
        json={"token": token, "notation": notation},
    )
    r.raise_for_status()
    return r.json()


def wait_for_turn(server: str, game_id: str, after_turn: int) -> dict:
    """Long-poll: wait until a new move is made."""
    r = httpx.get(
        f"{server}/api/game/{game_id}/wait",
        params={"after_turn": after_turn},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()


def ask_llm(llm_url: str, model: str, vision_text: str,
            temperature: float = 0.3) -> str:
    """Send the vision text to an LLM and get a move notation back."""
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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

    content = data["choices"][0]["message"]["content"].strip()
    return content


def extract_notation(llm_response: str, legal_notations: list[str]) -> str | None:
    """Try to extract a valid move notation from LLM response.

    First tries exact match, then fuzzy matching against legal moves.
    """
    # Clean up common LLM artifacts
    cleaned = llm_response.strip().strip('"').strip("'").strip("`")

    # Direct match
    if cleaned in legal_notations:
        return cleaned

    # Try case-insensitive match
    for notation in legal_notations:
        if cleaned.lower() == notation.lower():
            return notation

    # Try to find a legal notation substring in the response
    for notation in legal_notations:
        if notation in llm_response:
            return notation

    # Try replacing → with ->
    cleaned_arrow = cleaned.replace("→", "->")
    if cleaned_arrow in legal_notations:
        return cleaned_arrow
    for notation in legal_notations:
        if cleaned_arrow.lower() == notation.lower():
            return notation

    return None


def play_loop(server: str, game_id: str, token: str, color: str,
              llm_url: str, model: str):
    """Main play loop: wait for turn → get vision → ask LLM → submit move."""
    print(f"\n{'='*50}")
    print(f"  Rithmomachia LLM Client")
    print(f"  Playing as {color} in game {game_id}")
    print(f"  LLM: {llm_url}" + (f" ({model})" if model else ""))
    print(f"{'='*50}\n")

    last_turn = 0

    while True:
        # Get current state
        state = get_state(server, game_id)

        if state["status"] != "active":
            print(f"\nGame over: {state['status']}")
            break

        # If not our turn, wait
        if state["current_player"] != color:
            print(f"  Waiting for opponent (turn {state['turn']})...")
            state = wait_for_turn(server, game_id, state["move_count"])
            if state["status"] != "active":
                print(f"\nGame over: {state['status']}")
                break
            if state["current_player"] != color:
                continue

        print(f"\n--- Turn {state['turn']} ({color}) ---")

        # Get vision
        vision = get_vision(server, game_id, color)
        legal_notations = [m["notation"] for m in vision["legal_moves"]]

        if not legal_notations:
            print("  No legal moves available!")
            break

        print(f"  Legal moves: {len(legal_notations)}")
        if vision["threats"]:
            print(f"  Available captures: {len(vision['threats'])}")

        # Ask LLM with retry
        max_retries = 3
        move_made = False

        for attempt in range(max_retries):
            try:
                raw = ask_llm(llm_url, model, vision["raw_text"])
                print(f"  LLM says: {raw}")

                notation = extract_notation(raw, legal_notations)
                if notation is None:
                    print(f"  Could not match to legal move (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        continue
                    # Fall back to first legal move
                    notation = legal_notations[0]
                    print(f"  Falling back to: {notation}")

                result = submit_move(server, game_id, token, notation)
                if result["success"]:
                    print(f"  Played: {notation}")
                    if result["captures"]:
                        for cap in result["captures"]:
                            print(f"  CAPTURE: {cap['description']}")
                    if result.get("victory"):
                        print(f"\n  VICTORY! {result['victory']}")
                    move_made = True
                    break
                else:
                    print(f"  Server rejected: {result['error']} (attempt {attempt + 1})")

            except httpx.HTTPError as e:
                print(f"  HTTP error: {e} (attempt {attempt + 1})")
            except Exception as e:
                print(f"  Error: {e} (attempt {attempt + 1})")

        if not move_made:
            # Last resort: submit first legal move directly
            print(f"  All retries exhausted. Playing first legal move: {legal_notations[0]}")
            result = submit_move(server, game_id, token, legal_notations[0])
            if result["success"]:
                print(f"  Played: {legal_notations[0]}")

        time.sleep(0.5)  # Small delay between moves


def main():
    parser = argparse.ArgumentParser(description="Rithmomachia LLM Client")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="Game server URL")
    parser.add_argument("--game-id", help="Existing game ID to join")
    parser.add_argument("--new-game", action="store_true", help="Create a new game")
    parser.add_argument("--color", default="black", choices=["white", "black"])
    parser.add_argument("--name", default="LLM-Bot", help="Player name")
    parser.add_argument("--llm-url", default=DEFAULT_LLM, help="LLM API endpoint")
    parser.add_argument("--model", default="", help="Model name (for Ollama/OpenAI)")
    parser.add_argument("--temperature", type=float, default=0.3)
    args = parser.parse_args()

    if args.new_game:
        # Create a game with one side open for human
        other = "human" if args.color == "black" else "open"
        mine = "open" if args.color == "black" else "human"
        resp = create_game(args.server, white=mine if args.color == "white" else other,
                          black=mine if args.color == "black" else other)
        game_id = resp["id"]
        token = resp["white_token"] if args.color == "white" else resp["black_token"]
        print(f"Created game: {game_id}")
        print(f"Opponent can join at: {args.server}")

        # If we're open seat, join it
        if (args.color == "white" and mine == "open") or \
           (args.color == "black" and mine == "open"):
            token = join_game(args.server, game_id, args.color, args.name)
    elif args.game_id:
        game_id = args.game_id
        token = join_game(args.server, game_id, args.color, args.name)
        print(f"Joined game {game_id} as {args.color}")
    else:
        parser.error("Specify --game-id or --new-game")
        return

    play_loop(args.server, game_id, token, args.color,
              args.llm_url, args.model)


if __name__ == "__main__":
    main()
