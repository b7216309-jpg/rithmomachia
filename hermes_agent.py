"""Hermes Agent — Structured tool-use agent for Rithmomachia.

Unlike the raw-text LLM clients (llm_client.py, ai_vs_ai.py), Hermes uses
structured tool calls to interact with the game. The LLM decides *which*
tool to call and with *what* arguments — no fragile text extraction needed.

Works with any OpenAI-compatible API that supports tool/function calling
(OpenAI, Anthropic via proxy, Ollama, llama.cpp, vLLM, etc.).

Usage:
    # Start the game server:
    python run.py

    # Play as one side (join existing game):
    python hermes_agent.py --game-id <id> --color black \
        --api-url http://localhost:8080/v1/chat/completions

    # Create a new game and play as white:
    python hermes_agent.py --new-game --color white \
        --api-url http://localhost:8080/v1/chat/completions

    # AI vs AI with two Hermes agents:
    python hermes_agent.py --ai-vs-ai \
        --api-url http://localhost:8080/v1/chat/completions

    # Use Anthropic API directly:
    python hermes_agent.py --new-game --color white --provider anthropic \
        --model claude-sonnet-4-6 --api-key $ANTHROPIC_API_KEY
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx


# ═══════════════════════════════════════
# Tool Definitions (OpenAI function-calling format)
# ═══════════════════════════════════════

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_board_state",
            "description": (
                "Get the current game state: board positions, whose turn it is, "
                "captures so far, and progression status. Call this first to orient yourself."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_legal_actions",
            "description": (
                "Get all legal actions: standard moves, assault captures, ambush captures, "
                "and siege declarations. Each action includes its notation string."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_position",
            "description": (
                "Get a detailed strategic analysis of the current position: "
                "threats you can make, dangers from the opponent, capture opportunities, "
                "and which captures would advance your progression toward victory."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_move",
            "description": (
                "Submit your chosen move. Use the EXACT notation from get_legal_actions. "
                "Examples: 'R9 d2->d4', 'assault T36 d3->d5', 'ambush e5', 'siege d8'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "notation": {
                        "type": "string",
                        "description": "The move notation, exactly as shown in legal actions.",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of why you chose this move.",
                    },
                },
                "required": ["notation"],
            },
        },
    },
]

# Anthropic tool format
ANTHROPIC_TOOLS = [
    {
        "name": "get_board_state",
        "description": (
            "Get the current game state: board positions, whose turn it is, "
            "captures so far, and progression status."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_legal_actions",
        "description": (
            "Get all legal actions: standard moves, assault captures, ambush captures, "
            "and siege declarations. Each action includes its notation string."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "analyze_position",
        "description": (
            "Get detailed strategic analysis: threats, dangers, capture opportunities, "
            "and which captures advance your victory progression."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "submit_move",
        "description": (
            "Submit your chosen move using EXACT notation from get_legal_actions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "notation": {
                    "type": "string",
                    "description": "Move notation, e.g. 'R9 d2->d4'",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of your choice.",
                },
            },
            "required": ["notation"],
        },
    },
]


SYSTEM_PROMPT = """You are a Rithmomachia player — a medieval mathematical strategy game on an 8x16 board.

GAME RULES:
- Pieces have shapes (Round=1 sq move, Triangle=2 sq, Square=3 sq, Pyramid=variable) and numeric values.
- Capture types: Encounter (land on equal-value enemy), Assault (your value × distance = their value),
  Ambush (friendly pieces that could reach a square sum to the enemy's value), Siege (fully surround enemy).
- WIN by capturing pieces whose values form 3+ length arithmetic, geometric, or harmonic progressions.

YOUR APPROACH:
1. First call get_board_state to see the current position.
2. Then call get_legal_actions to see your options.
3. Optionally call analyze_position for deeper strategic insight.
4. Finally call submit_move with your chosen notation.

STRATEGY TIPS:
- Prioritize captures that give you values useful for progressions.
- Arithmetic progressions: equal differences (e.g., 2,4,6 or 3,6,9).
- Geometric progressions: equal ratios (e.g., 2,4,8 or 3,9,27).
- Harmonic progressions: reciprocals form arithmetic seq (e.g., 2,3,6).
- Protect your pieces from opponent captures.
- Control the center of the board.
"""


# ═══════════════════════════════════════
# Game Server Interface
# ═══════════════════════════════════════

class GameInterface:
    """Wraps game server API calls for the agent's tool execution."""

    def __init__(self, server: str, game_id: str, token: str, color: str):
        self.server = server
        self.game_id = game_id
        self.token = token
        self.color = color
        self.client = httpx.Client(timeout=60.0)

    def _api(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.server}/api/game/{self.game_id}{path}"
        r = self.client.request(method, url, **kwargs)
        r.raise_for_status()
        return r.json()

    def get_board_state(self) -> dict:
        state = self._api("GET", "/state")
        # Return a focused summary for the LLM
        return {
            "turn": state["turn"],
            "your_color": self.color,
            "current_player": state["current_player"],
            "status": state["status"],
            "move_count": state["move_count"],
            "white_captures": state["captures"]["white"],
            "black_captures": state["captures"]["black"],
            "white_progressions": state["progressions"]["white"],
            "black_progressions": state["progressions"]["black"],
            "piece_count": {
                "white": sum(1 for p in state["board"] if p["color"] == "white" and not p["captured"]),
                "black": sum(1 for p in state["board"] if p["color"] == "black" and not p["captured"]),
            },
            "last_move": state.get("last_move"),
        }

    def get_legal_actions(self) -> dict:
        legal = self._api("GET", "/legal")
        # Compact format: just what the LLM needs
        moves = []
        for m in legal["moves"]:
            entry = {"notation": m["notation"], "piece": m["piece_label"], "from": m["from_pos"], "to": m["to_pos"]}
            if m["is_capture"]:
                entry["capture"] = True
            moves.append(entry)

        assaults = [{"type": "assault", "description": a["description"],
                     "captures_value": a["captured_value"]} for a in legal["assaults"]]
        ambushes = [{"type": "ambush", "description": a["description"],
                     "captures_value": a["captured_value"]} for a in legal["ambushes"]]
        sieges = [{"type": "siege", "description": s["description"],
                   "captures_value": s["captured_value"]} for s in legal["sieges"]]

        result = {"moves": moves, "total_moves": len(moves)}
        if assaults:
            result["assaults"] = assaults
        if ambushes:
            result["ambushes"] = ambushes
        if sieges:
            result["sieges"] = sieges
        return result

    def analyze_position(self) -> dict:
        vision = self._api("GET", "/vision", params={"color": self.color})
        # Return the structured layers
        return {
            "threats": vision.get("threats", []),
            "dangers": vision.get("dangers", []),
            "captures_and_progressions": vision.get("captures_and_progressions", {}),
            "context": vision.get("context", {}),
        }

    def submit_move(self, notation: str) -> dict:
        result = self._api("POST", "/move", json={
            "token": self.token,
            "notation": notation,
        })
        return {
            "success": result["success"],
            "error": result.get("error"),
            "notation": result.get("notation"),
            "captures": result.get("captures", []),
            "victory": result.get("victory"),
            "victory_type": result.get("victory_type", "none"),
        }

    def wait_for_turn(self, after_turn: int) -> dict:
        return self._api("GET", "/wait", params={"after_turn": after_turn})

    def execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool call and return JSON result."""
        if name == "get_board_state":
            return json.dumps(self.get_board_state(), indent=2)
        elif name == "get_legal_actions":
            return json.dumps(self.get_legal_actions(), indent=2)
        elif name == "analyze_position":
            return json.dumps(self.analyze_position(), indent=2)
        elif name == "submit_move":
            return json.dumps(self.submit_move(args.get("notation", "")), indent=2)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})


# ═══════════════════════════════════════
# LLM Providers
# ═══════════════════════════════════════

def call_openai_compatible(api_url: str, model: str, messages: list,
                           tools: list, temperature: float, api_key: str = "") -> dict:
    """Call an OpenAI-compatible chat/completions endpoint with tools."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "messages": messages,
        "tools": tools,
        "temperature": temperature,
        "max_tokens": 1024,
    }
    if model:
        payload["model"] = model

    r = httpx.post(api_url, json=payload, headers=headers, timeout=120.0)
    r.raise_for_status()
    return r.json()


def call_anthropic(api_key: str, model: str, messages: list,
                   tools: list, system: str, temperature: float) -> dict:
    """Call Anthropic Messages API with tool use."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 1024,
        "temperature": temperature,
        "system": system,
        "messages": messages,
        "tools": tools,
    }
    r = httpx.post("https://api.anthropic.com/v1/messages", json=payload,
                   headers=headers, timeout=120.0)
    r.raise_for_status()
    return r.json()


# ═══════════════════════════════════════
# Agent Loop
# ═══════════════════════════════════════

def run_agent_turn_openai(api_url: str, model: str, api_key: str,
                          temperature: float, game: GameInterface) -> bool:
    """Run one turn using OpenAI-compatible tool calling. Returns True if move was made."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"It's your turn. You are playing {game.color}. Analyze the position and make your move."},
    ]

    for step in range(8):  # Max tool-call rounds
        resp = call_openai_compatible(api_url, model, messages, TOOLS, temperature, api_key)
        choice = resp["choices"][0]
        msg = choice["message"]

        # If the model wants to call tools
        tool_calls = msg.get("tool_calls", [])
        if not tool_calls:
            # Model responded with text — no tool call. Prompt it to use tools.
            print(f"    Text: {msg.get('content', '')[:100]}")
            messages.append(msg)
            messages.append({"role": "user", "content": "Please use the submit_move tool to make your move."})
            continue

        messages.append(msg)

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"]) if tc["function"].get("arguments") else {}

            print(f"    Tool: {fn_name}({', '.join(f'{k}={v!r}' for k,v in fn_args.items()) if fn_args else ''})")

            result = game.execute_tool(fn_name, fn_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

            if fn_name == "submit_move":
                result_data = json.loads(result)
                if result_data.get("success"):
                    if fn_args.get("reasoning"):
                        print(f"    Reason: {fn_args['reasoning']}")
                    return True
                else:
                    print(f"    Move rejected: {result_data.get('error')}")

    print("    Agent exhausted tool-call budget without making a move.")
    return False


def run_agent_turn_anthropic(api_key: str, model: str,
                              temperature: float, game: GameInterface) -> bool:
    """Run one turn using Anthropic Messages API with tool use."""
    messages = [
        {"role": "user", "content": f"It's your turn. You are playing {game.color}. Analyze the position and make your move."},
    ]

    for step in range(8):
        resp = call_anthropic(api_key, model, messages, ANTHROPIC_TOOLS,
                              SYSTEM_PROMPT, temperature)

        # Process response content blocks
        tool_uses = []
        text_parts = []
        for block in resp.get("content", []):
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_uses.append(block)

        if text_parts:
            print(f"    Think: {''.join(text_parts)[:120]}")

        if not tool_uses:
            messages.append({"role": "assistant", "content": resp["content"]})
            messages.append({"role": "user", "content": "Please use the submit_move tool."})
            continue

        messages.append({"role": "assistant", "content": resp["content"]})

        tool_results = []
        move_made = False

        for tu in tool_uses:
            fn_name = tu["name"]
            fn_args = tu.get("input", {})
            tool_id = tu["id"]

            print(f"    Tool: {fn_name}({', '.join(f'{k}={v!r}' for k,v in fn_args.items()) if fn_args else ''})")

            result = game.execute_tool(fn_name, fn_args)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result,
            })

            if fn_name == "submit_move":
                result_data = json.loads(result)
                if result_data.get("success"):
                    if fn_args.get("reasoning"):
                        print(f"    Reason: {fn_args['reasoning']}")
                    move_made = True
                else:
                    print(f"    Move rejected: {result_data.get('error')}")

        messages.append({"role": "user", "content": tool_results})

        if move_made:
            return True

    print("    Agent exhausted tool-call budget.")
    return False


def play_loop(game: GameInterface, run_turn_fn, max_turns: int = 200, delay: float = 1.0):
    """Main play loop: wait for turn -> agent decides -> submit move -> repeat."""
    print(f"\n{'='*55}")
    print(f"  Hermes Agent — Rithmomachia")
    print(f"  Playing as: {game.color}")
    print(f"  Game ID:    {game.game_id}")
    print(f"{'='*55}\n")

    last_move_count = 0

    for turn in range(max_turns):
        # Check state
        state_resp = game._api("GET", "/state")
        status = state_resp["status"]

        if status != "active":
            print(f"\nGame over: {status}")
            print(f"Moves: {state_resp['move_count']}")
            print(f"W captures: {state_resp['captures']['white']}")
            print(f"B captures: {state_resp['captures']['black']}")
            break

        # Wait for our turn
        if state_resp["current_player"] != game.color:
            print(f"  Waiting for opponent (move {state_resp['move_count']})...")
            state_resp = game.wait_for_turn(state_resp["move_count"])
            if state_resp["status"] != "active":
                print(f"\nGame over: {state_resp['status']}")
                break
            if state_resp["current_player"] != game.color:
                continue

        print(f"\n--- Turn {state_resp['turn']} ({game.color}) ---")
        success = run_turn_fn(game)

        if not success:
            # Fallback: pick first legal move
            legal = game.get_legal_actions()
            if legal["moves"]:
                notation = legal["moves"][0]["notation"]
                print(f"    Fallback: {notation}")
                game.submit_move(notation)

        if delay > 0:
            time.sleep(delay)

    print("\nHermes Agent done.")


# ═══════════════════════════════════════
# AI vs AI Mode
# ═══════════════════════════════════════

def play_ai_vs_ai(server: str, api_url: str, model: str, api_key: str,
                  provider: str, temperature: float, delay: float, max_turns: int):
    """Two Hermes agents play each other."""
    # Create game
    r = httpx.post(f"{server}/api/game/new", json={
        "white": "open", "black": "open",
        "white_name": "Hermes-W", "black_name": "Hermes-B",
        "white_description": "Structured tool-use agent (white)",
        "black_description": "Structured tool-use agent (black)",
    })
    r.raise_for_status()
    data = r.json()
    game_id = data["id"]

    print(f"\n{'='*55}")
    print(f"  Hermes Agent — AI vs AI")
    print(f"  Game ID: {game_id}")
    print(f"  Spectate: open browser to {server}, click Spectate, enter {game_id}")
    print(f"{'='*55}\n")

    white = GameInterface(server, game_id, data["white_token"], "white")
    black = GameInterface(server, game_id, data["black_token"], "black")

    if provider == "anthropic":
        run_white = lambda g: run_agent_turn_anthropic(api_key, model, temperature, g)
        run_black = lambda g: run_agent_turn_anthropic(api_key, model, temperature, g)
    else:
        run_white = lambda g: run_agent_turn_openai(api_url, model, api_key, temperature, g)
        run_black = lambda g: run_agent_turn_openai(api_url, model, api_key, temperature, g)

    for turn in range(max_turns):
        state = white._api("GET", "/state")
        if state["status"] != "active":
            print(f"\nGame over: {state['status']} after {state['move_count']} moves")
            break

        current = state["current_player"]
        agent = white if current == "white" else black
        run_fn = run_white if current == "white" else run_black

        print(f"\n--- Turn {state['turn']} ({current}) ---")
        success = run_fn(agent)

        if not success:
            legal = agent.get_legal_actions()
            if legal["moves"]:
                notation = legal["moves"][0]["notation"]
                print(f"    Fallback: {notation}")
                agent.submit_move(notation)

        if delay > 0:
            time.sleep(delay)


# ═══════════════════════════════════════
# CLI
# ═══════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Hermes Agent — Structured tool-use Rithmomachia player",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--server", default="http://localhost:8001", help="Game server URL")
    parser.add_argument("--game-id", help="Join an existing game")
    parser.add_argument("--new-game", action="store_true", help="Create a new game")
    parser.add_argument("--ai-vs-ai", action="store_true", help="Two agents play each other")
    parser.add_argument("--color", default="black", choices=["white", "black"])
    parser.add_argument("--name", default="Hermes", help="Player name")
    parser.add_argument("--description", default="Structured tool-use agent",
                        help="Player description")

    parser.add_argument("--provider", default="openai", choices=["openai", "anthropic"],
                        help="LLM provider (openai = any OpenAI-compatible endpoint)")
    parser.add_argument("--api-url", default="http://localhost:8080/v1/chat/completions",
                        help="API endpoint (for openai provider)")
    parser.add_argument("--api-key", default="", help="API key")
    parser.add_argument("--model", default="", help="Model name")
    parser.add_argument("--temperature", type=float, default=0.3)

    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between moves")
    parser.add_argument("--max-turns", type=int, default=200)
    args = parser.parse_args()

    if args.ai_vs_ai:
        play_ai_vs_ai(
            args.server, args.api_url, args.model, args.api_key,
            args.provider, args.temperature, args.delay, args.max_turns,
        )
        return

    # Single agent mode
    if args.new_game:
        other = "human"
        mine = "open"
        w = mine if args.color == "white" else other
        b = mine if args.color == "black" else other
        r = httpx.post(f"{args.server}/api/game/new", json={"white": w, "black": b})
        r.raise_for_status()
        data = r.json()
        game_id = data["id"]
        token = data["white_token"] if args.color == "white" else data["black_token"]

        # Join the open seat
        r2 = httpx.post(f"{args.server}/api/game/{game_id}/join",
                        json={"color": args.color, "name": args.name, "description": args.description})
        r2.raise_for_status()
        token = r2.json()["token"]
        print(f"Created game: {game_id}")

    elif args.game_id:
        game_id = args.game_id
        r = httpx.post(f"{args.server}/api/game/{game_id}/join",
                       json={"color": args.color, "name": args.name, "description": args.description})
        r.raise_for_status()
        token = r.json()["token"]
        print(f"Joined game {game_id} as {args.color}")
    else:
        parser.error("Specify --game-id, --new-game, or --ai-vs-ai")
        return

    game = GameInterface(args.server, game_id, token, args.color)

    if args.provider == "anthropic":
        run_fn = lambda g: run_agent_turn_anthropic(args.api_key, args.model, args.temperature, g)
    else:
        run_fn = lambda g: run_agent_turn_openai(args.api_url, args.model, args.api_key, args.temperature, g)

    play_loop(game, run_fn, args.max_turns, args.delay)


if __name__ == "__main__":
    main()
