"""Capture logic for the four Rithmomachia capture types.

Each function checks whether a specific capture type applies and returns
Capture objects. The game orchestrator calls these after a move to determine
what was captured.
"""

from __future__ import annotations

from itertools import combinations

from engine.models import (
    Color, Piece, Capture, CaptureType, GameState,
)
from engine.board import is_in_bounds, is_path_clear


def check_encounter(state: GameState, piece: Piece,
                    to_row: int, to_col: int) -> Capture | None:
    """Check for encounter capture: piece moves onto an enemy of equal value.

    The move itself must be legal (correct range, clear path) — that's
    validated by board.py before this is called.
    """
    target = state.piece_at(to_row, to_col)
    if target is None:
        return None
    if target.color == piece.color:
        return None
    if target.value != piece.value:
        return None

    return Capture(
        capture_type=CaptureType.ENCOUNTER,
        captured_piece_id=target.id,
        captured_value=target.value,
        capturing_piece_ids=[piece.id],
        description=f"{piece.value} = {target.value}",
    )


def check_assault(state: GameState, piece: Piece,
                  target: Piece) -> Capture | None:
    """Check for assault capture: value × distance relationship.

    Assault requires:
    - Pieces are on the same row or column (orthogonal line of sight)
    - The path between them is clear
    - (attacker value × distance = target value) OR (target value × distance = attacker value)

    The attacking piece does NOT move to the target's square.
    """
    if piece.color == target.color:
        return None

    # Must be on the same row or column
    if piece.row != target.row and piece.col != target.col:
        return None

    # Calculate distance (number of squares between, not counting piece's own)
    if piece.row == target.row:
        distance = abs(piece.col - target.col)
    else:
        distance = abs(piece.row - target.row)

    if distance == 0:
        return None

    # Path must be clear between the two pieces
    if not is_path_clear(state, piece.row, piece.col, target.row, target.col):
        return None

    # Check the multiplication relationship.
    # For pyramids, also check each component's value.
    values_to_check = [piece.value]
    if piece.shape.value == "pyramid" and piece.components:
        values_to_check.extend(v for _, v in piece.components)

    desc = None
    for val in values_to_check:
        if val * distance == target.value:
            desc = f"{val} × {distance} = {target.value}"
            break
        if target.value * distance == val:
            desc = f"{target.value} × {distance} = {val}"
            break

    if desc is None:
        return None

    return Capture(
        capture_type=CaptureType.ASSAULT,
        captured_piece_id=target.id,
        captured_value=target.value,
        capturing_piece_ids=[piece.id],
        description=desc,
    )


def check_ambush(state: GameState, color: Color) -> list[Capture]:
    """Check for ambush captures: two+ friendly pieces whose values sum to an enemy's value.

    For each enemy piece, check if two or more of the current player's pieces
    can reach the enemy's square (within their move range, clear path) and
    their values sum to the enemy's value.

    Returns all possible ambush captures found.
    """
    captures: list[Capture] = []
    friendly = state.pieces_by_color(color)
    enemies = state.pieces_by_color(color.opposite)

    for enemy in enemies:
        # Find all friendly pieces that can reach the enemy's square
        reachable: list[Piece] = []
        for fp in friendly:
            if _can_reach(state, fp, enemy.row, enemy.col):
                reachable.append(fp)

        if len(reachable) < 2:
            continue

        # Check all combinations of 2+ reachable pieces for sum match
        for size in range(2, len(reachable) + 1):
            for combo in combinations(reachable, size):
                value_sum = sum(p.value for p in combo)
                if value_sum == enemy.value:
                    ids = [p.id for p in combo]
                    vals = " + ".join(str(p.value) for p in combo)
                    captures.append(Capture(
                        capture_type=CaptureType.AMBUSH,
                        captured_piece_id=enemy.id,
                        captured_value=enemy.value,
                        capturing_piece_ids=ids,
                        description=f"{vals} = {enemy.value}",
                    ))

    return captures


def _can_reach(state: GameState, piece: Piece, target_row: int, target_col: int) -> bool:
    """Check if a piece could move to the target square (within range, clear path, orthogonal)."""
    if piece.row != target_row and piece.col != target_col:
        return False  # Not orthogonal

    if piece.row == target_row:
        distance = abs(piece.col - target_col)
    else:
        distance = abs(piece.row - target_row)

    if distance == 0 or distance > piece.shape.move_range:
        return False

    return is_path_clear(state, piece.row, piece.col, target_row, target_col)


def check_siege(state: GameState, color: Color) -> list[Capture]:
    """Check for siege captures after a player's turn.

    An enemy piece is captured by siege if ALL of its orthogonal neighbors
    are occupied by the current player's pieces or are board edges.
    The besieging pieces don't need specific values.
    """
    captures: list[Capture] = []
    enemies = state.pieces_by_color(color.opposite)

    for enemy in enemies:
        besieging_ids: list[int] = []
        is_sieged = True

        for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            adj_row, adj_col = enemy.row + dr, enemy.col + dc

            if not is_in_bounds(adj_row, adj_col):
                # Board edge counts as blocking
                continue

            neighbor = state.piece_at(adj_row, adj_col)
            if neighbor is None:
                is_sieged = False
                break
            elif neighbor.color == color:
                besieging_ids.append(neighbor.id)
            else:
                # Friendly piece (from enemy's perspective) doesn't block siege
                is_sieged = False
                break

        if is_sieged and besieging_ids:
            captures.append(Capture(
                capture_type=CaptureType.SIEGE,
                captured_piece_id=enemy.id,
                captured_value=enemy.value,
                capturing_piece_ids=besieging_ids,
                description=f"siege on {enemy.label}",
            ))

    return captures


def find_all_captures_for_move(state: GameState, piece: Piece,
                               to_row: int, to_col: int) -> list[Capture]:
    """Find all captures that result from a piece moving to (to_row, to_col).

    This checks encounter (at destination) and returns it if found.
    Ambush and siege are checked separately after the move is applied,
    since they depend on the new board position.
    """
    captures: list[Capture] = []

    # Encounter: moving onto an enemy of equal value
    enc = check_encounter(state, piece, to_row, to_col)
    if enc:
        captures.append(enc)

    return captures


def find_assault_targets(state: GameState, piece: Piece) -> list[Capture]:
    """Find all enemies this piece can capture by assault from its current position."""
    captures: list[Capture] = []
    enemies = state.pieces_by_color(piece.color.opposite)

    for enemy in enemies:
        cap = check_assault(state, piece, enemy)
        if cap:
            captures.append(cap)

    return captures
