"""LLM-ready board representation builder for Rithmomachia.

Builds a 6-layer hybrid representation that gives an LLM "eyes" on the game
without requiring it to do spatial reasoning or math. The engine computes
FACTS, never EVALUATIONS.

Layers:
1. Compact grid — Numeric values on an 8×16 grid
2. Threats — Viable captures the player can make this turn
3. Dangers — Captures the opponent can make next turn
4. Captures & Progressions — Captured values + what completes a progression
5. Enriched moves — Every legal move with factual consequences
6. Context — Turn number, game phase, last opponent move
"""

from __future__ import annotations

from engine.models import Color, Shape, GameState, Piece
from engine.board import all_legal_moves, is_path_clear, is_in_bounds, ROWS, COLS
from engine.captures import (
    check_encounter, check_assault, check_ambush, check_siege,
    find_assault_targets,
)
from engine.victory import find_progressions, values_needed_for_progression
from engine.notation import format_move


def build_vision(state: GameState, color: Color) -> dict:
    """Build the complete 6-layer vision for the given player.

    Returns both structured JSON and a raw_text field ready for LLM prompts.
    """
    grid = _build_compact_grid(state)
    threats = _build_threats(state, color)
    dangers = _build_dangers(state, color)
    caps_and_progs = _build_captures_and_progressions(state, color)
    enriched = _build_enriched_moves(state, color)
    context = _build_context(state, color)

    raw_text = _format_raw_text(
        state, color, grid, threats, dangers, caps_and_progs, enriched, context
    )

    return {
        "turn": state.turn,
        "color": color.value,
        "compact_grid": grid,
        "threats": threats,
        "dangers": dangers,
        "captures_and_progressions": caps_and_progs,
        "legal_moves": enriched,
        "context": context,
        "raw_text": raw_text,
    }


# ── Layer 1: Compact Grid ──

def _build_compact_grid(state: GameState) -> str:
    """Render the board as a text grid with piece symbols and values."""
    lines = []
    # Header
    lines.append("   " + "  ".join(f" {chr(ord('a') + c)} " for c in range(COLS)))

    for row in range(ROWS, 0, -1):
        row_str = f"{row:2d} "
        cells = []
        for col in range(COLS):
            piece = state.piece_at(row, col)
            if piece is None:
                cells.append(" ·  ")
            else:
                sym = piece.symbol
                val = str(piece.value)
                if len(val) == 1:
                    cells.append(f" {sym}{val} ")
                elif len(val) == 2:
                    cells.append(f"{sym}{val} ")
                else:
                    cells.append(f"{sym}{val}")
        row_str += "".join(cells)

        # Mark frontier
        if row == 9:
            lines.append(row_str)
            lines.append("   " + "─" * (COLS * 4))
        else:
            lines.append(row_str)

    return "\n".join(lines)


# ── Layer 2: Threats ──

def _build_threats(state: GameState, color: Color) -> list[dict]:
    """Find all captures the player can make this turn."""
    threats = []

    # Encounter captures (from legal moves that land on equal-value enemies)
    moves = all_legal_moves(state, color)
    for move in moves:
        target = state.piece_at(move.to_row, move.to_col)
        if target and target.color != color and target.value == state.piece_by_id(move.piece_id).value:
            piece = state.piece_by_id(move.piece_id)
            threats.append({
                "piece": piece.label,
                "move": f"{piece.position_str}->{_pos(move.to_row, move.to_col)}",
                "capture": "encounter",
                "target": target.label,
                "math": f"{piece.value}={target.value}",
            })

    # Assault captures
    for piece in state.pieces_by_color(color):
        for cap in find_assault_targets(state, piece):
            target = state.piece_by_id(cap.captured_piece_id)
            threats.append({
                "piece": piece.label,
                "move": f"{piece.position_str} (stays)",
                "capture": "assault",
                "target": target.label,
                "math": cap.description,
            })

    # Ambush captures
    for cap in check_ambush(state, color):
        target = state.piece_by_id(cap.captured_piece_id)
        pieces_str = ", ".join(
            state.piece_by_id(pid).label for pid in cap.capturing_piece_ids
        )
        threats.append({
            "piece": pieces_str,
            "move": "(ambush, no movement)",
            "capture": "ambush",
            "target": target.label,
            "math": cap.description,
        })

    # Siege captures
    for cap in check_siege(state, color):
        target = state.piece_by_id(cap.captured_piece_id)
        threats.append({
            "piece": f"siege by {len(cap.capturing_piece_ids)} pieces",
            "move": "(siege, no movement)",
            "capture": "siege",
            "target": target.label,
            "math": cap.description,
        })

    return threats


# ── Layer 3: Dangers ──

def _build_dangers(state: GameState, color: Color) -> list[dict]:
    """Find captures the opponent could make next turn."""
    opp = color.opposite
    dangers = []

    # Opponent's encounter captures
    opp_moves = all_legal_moves(state, opp)
    for move in opp_moves:
        target = state.piece_at(move.to_row, move.to_col)
        if target and target.color == color:
            piece = state.piece_by_id(move.piece_id)
            if piece.value == target.value:
                dangers.append({
                    "piece": target.label,
                    "threat_from": piece.label,
                    "capture_type": "encounter",
                    "math": f"{piece.value}={target.value}",
                })

    # Opponent's assault captures on our pieces
    for opp_piece in state.pieces_by_color(opp):
        for cap in find_assault_targets(state, opp_piece):
            target = state.piece_by_id(cap.captured_piece_id)
            if target.color == color:
                dangers.append({
                    "piece": target.label,
                    "threat_from": opp_piece.label,
                    "capture_type": "assault",
                    "math": cap.description,
                })

    # Opponent ambushes
    for cap in check_ambush(state, opp):
        target = state.piece_by_id(cap.captured_piece_id)
        if target.color == color:
            dangers.append({
                "piece": target.label,
                "threat_from": "ambush",
                "capture_type": "ambush",
                "math": cap.description,
            })

    # Opponent sieges
    for cap in check_siege(state, opp):
        target = state.piece_by_id(cap.captured_piece_id)
        if target.color == color:
            dangers.append({
                "piece": target.label,
                "threat_from": "siege",
                "capture_type": "siege",
                "math": cap.description,
            })

    return dangers


# ── Layer 4: Captures & Progressions ──

def _build_captures_and_progressions(state: GameState, color: Color) -> dict:
    """Analyze captured values and what's needed for victory."""
    my_captures = state.captured_values(color)
    opp_captures = state.captured_values(color.opposite)

    # Enemy pieces still alive (values the player could capture)
    enemy_alive = [p.value for p in state.pieces_by_color(color.opposite)]

    # Find what values would complete a progression
    needed = values_needed_for_progression(my_captures, enemy_alive)

    # Find which enemy pieces have those values
    enemy_targets = []
    for val, descs in needed.items():
        matching_pieces = [
            p for p in state.pieces_by_color(color.opposite) if p.value == val
        ]
        for p in matching_pieces:
            enemy_targets.append({
                "value": val,
                "piece": p.label,
                "progressions": descs,
            })

    # Current progressions
    my_progs = find_progressions(my_captures)
    opp_progs = find_progressions(opp_captures)

    return {
        "your_captures": sorted(my_captures),
        "opponent_captures": sorted(opp_captures),
        "your_progressions": [p.description for p in my_progs],
        "opponent_progressions": [p.description for p in opp_progs],
        "values_for_victory": {str(v): descs for v, descs in needed.items()},
        "enemy_pieces_with_needed_values": enemy_targets,
    }


# ── Layer 5: Enriched Moves ──

def _build_enriched_moves(state: GameState, color: Color) -> list[dict]:
    """Every legal move with factual consequences."""
    moves = all_legal_moves(state, color)
    enriched = []

    for move in moves:
        piece = state.piece_by_id(move.piece_id)
        target = state.piece_at(move.to_row, move.to_col)
        notation = format_move(piece, move.to_row, move.to_col)

        entry = {
            "notation": notation,
            "capture": None,
            "notes": [],
        }

        # Check encounter
        if target and target.color != color and target.value == piece.value:
            entry["capture"] = {
                "type": "encounter",
                "target": target.label,
                "math": f"{piece.value}={target.value}",
            }

        # Note about direction
        if move.to_row > piece.row:
            entry["notes"].append("advances toward opponent")
        elif move.to_row < piece.row:
            entry["notes"].append("retreats")

        # Check what assaults become possible from new position
        # (simulate the move mentally)
        new_assaults = _check_assaults_from_position(
            state, piece, move.to_row, move.to_col
        )
        if new_assaults:
            for a in new_assaults:
                t = state.piece_by_id(a.captured_piece_id)
                entry["notes"].append(
                    f"enables assault on {t.label}: {a.description}"
                )

        entry["notes"] = "; ".join(entry["notes"]) if entry["notes"] else ""
        enriched.append(entry)

    # Also include assault declarations
    for piece in state.pieces_by_color(color):
        for cap in find_assault_targets(state, piece):
            target = state.piece_by_id(cap.captured_piece_id)
            enriched.append({
                "notation": f"assault {piece.notation_prefix}{piece.value} {piece.position_str}->{target.position_str}",
                "capture": {
                    "type": "assault",
                    "target": target.label,
                    "math": cap.description,
                },
                "notes": "assault capture (piece stays in place)",
            })

    # Ambush declarations
    for cap in check_ambush(state, color):
        target = state.piece_by_id(cap.captured_piece_id)
        enriched.append({
            "notation": f"ambush {target.position_str}",
            "capture": {
                "type": "ambush",
                "target": target.label,
                "math": cap.description,
            },
            "notes": "ambush capture (no movement)",
        })

    # Siege declarations
    for cap in check_siege(state, color):
        target = state.piece_by_id(cap.captured_piece_id)
        enriched.append({
            "notation": f"siege {target.position_str}",
            "capture": {
                "type": "siege",
                "target": target.label,
                "math": cap.description,
            },
            "notes": "siege capture (target fully surrounded)",
        })

    return enriched


def _check_assaults_from_position(state: GameState, piece: Piece,
                                   new_row: int, new_col: int) -> list:
    """Check what assaults a piece could make from a hypothetical position."""
    results = []
    enemies = state.pieces_by_color(piece.color.opposite)

    for enemy in enemies:
        # Must be orthogonal
        if enemy.row != new_row and enemy.col != new_col:
            continue

        if enemy.row == new_row:
            distance = abs(enemy.col - new_col)
        else:
            distance = abs(enemy.row - new_row)

        if distance == 0:
            continue

        # Check multiplication
        if piece.value * distance == enemy.value or enemy.value * distance == piece.value:
            # Check path clear (approximate — doesn't account for piece's old position)
            if is_path_clear(state, new_row, new_col, enemy.row, enemy.col):
                from engine.models import Capture, CaptureType
                if piece.value * distance == enemy.value:
                    desc = f"{piece.value} × {distance} = {enemy.value}"
                else:
                    desc = f"{enemy.value} × {distance} = {piece.value}"
                results.append(Capture(
                    capture_type=CaptureType.ASSAULT,
                    captured_piece_id=enemy.id,
                    captured_value=enemy.value,
                    capturing_piece_ids=[piece.id],
                    description=desc,
                ))

    return results


# ── Layer 6: Context ──

def _build_context(state: GameState, color: Color) -> dict:
    """Game context: phase, last move, turn info."""
    # Determine game phase
    total_pieces = len(state.active_pieces)
    if total_pieces >= 44:
        phase = "opening"
    elif total_pieces >= 30:
        phase = "midgame"
    else:
        phase = "endgame"

    last_move = None
    if state.move_history:
        m = state.move_history[-1]
        last_move = m.notation

    return {
        "phase": phase,
        "turn": state.turn,
        "total_pieces": total_pieces,
        "your_pieces": len(state.pieces_by_color(color)),
        "opponent_pieces": len(state.pieces_by_color(color.opposite)),
        "draw_counter": state.draw_counter,
        "last_opponent_move": last_move,
    }


# ── Raw text formatter ──

def _format_raw_text(state, color, grid, threats, dangers,
                     caps_progs, enriched, context) -> str:
    """Format the 6 layers into a single text block for LLM consumption."""
    lines = []
    player = color.value.upper()

    lines.append(f"{'═' * 40}")
    lines.append(f"  TURN {context['turn']} · {player} TO MOVE")
    lines.append(f"  Phase: {context['phase']} | Pieces: {context['your_pieces']} vs {context['opponent_pieces']} | Draw counter: {context['draw_counter']}/50")
    if context["last_opponent_move"]:
        lines.append(f"  Last opponent move: {context['last_opponent_move']}")
    lines.append(f"{'═' * 40}")

    lines.append("")
    lines.append("BOARD")
    lines.append(grid)

    if threats:
        lines.append("")
        lines.append(f"YOUR CAPTURES AVAILABLE ({len(threats)}):")
        for t in threats:
            lines.append(f"  {t['capture'].upper()}: {t['piece']} → {t['target']} [{t['math']}]")

    if dangers:
        lines.append("")
        lines.append(f"OPPONENT THREATS ({len(dangers)}):")
        for d in dangers:
            lines.append(f"  {d['capture_type'].upper()}: {d['piece']} threatened by {d['threat_from']} [{d['math']}]")

    cap_vals = caps_progs["your_captures"]
    opp_vals = caps_progs["opponent_captures"]
    lines.append("")
    lines.append(f"YOUR CAPTURES: {cap_vals if cap_vals else 'none'}")
    lines.append(f"OPPONENT CAPTURES: {opp_vals if opp_vals else 'none'}")

    if caps_progs["your_progressions"]:
        lines.append(f"YOUR PROGRESSIONS: {', '.join(caps_progs['your_progressions'])}")
    if caps_progs["opponent_progressions"]:
        lines.append(f"OPPONENT PROGRESSIONS: {', '.join(caps_progs['opponent_progressions'])}")

    needed = caps_progs["values_for_victory"]
    targets = caps_progs["enemy_pieces_with_needed_values"]
    if needed:
        lines.append("")
        lines.append("VALUES NEEDED FOR VICTORY:")
        for val, descs in needed.items():
            lines.append(f"  Capture value {val} → {', '.join(descs)}")
        if targets:
            lines.append("  Enemy pieces with needed values:")
            for t in targets:
                lines.append(f"    {t['piece']} (value {t['value']}) → {', '.join(t['progressions'])}")

    lines.append("")
    lines.append(f"LEGAL MOVES ({len(enriched)}):")
    for m in enriched:
        cap_str = ""
        if m["capture"]:
            cap_str = f" [CAPTURE {m['capture']['type']}: {m['capture']['target']}, {m['capture']['math']}]"
        notes_str = f"  -- {m['notes']}" if m["notes"] else ""
        lines.append(f"  {m['notation']}{cap_str}{notes_str}")

    lines.append("")
    lines.append("Respond with ONLY the move notation (e.g., 'R9 d2->d4' or 'assault T36 d3->d5').")

    return "\n".join(lines)


def _pos(row: int, col: int) -> str:
    return f"{chr(ord('a') + col)}{row}"
