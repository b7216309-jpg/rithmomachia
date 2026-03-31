"""Algebraic notation parser/formatter for Rithmomachia moves.

Notation format: "{ShapePrefix}{Value} {from}→{to}"
Examples:
  "R9 d2→d3"    — Round piece value 9, moves from d2 to d3
  "T36 d3→d5"   — Triangle value 36, moves from d3 to d5
  "S49 e3→e6"   — Square value 49, moves from e3 to e6

For captures declared without movement (ambush, assault, siege):
  "ambush e5"        — Declare ambush capture on piece at e5
  "assault T36 d3→e5" — Assault from T36 at d3 targeting e5
  "siege e5"         — Declare siege on piece at e5

The parser is lenient: it accepts "→", "->", or " " as the move separator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from engine.models import Shape, GameState, Piece


SHAPE_PREFIXES = {
    "R": Shape.ROUND,
    "T": Shape.TRIANGLE,
    "S": Shape.SQUARE,
    "P": Shape.PYRAMID,
}

# Match patterns like "R9 d2→d3", "R9 d2->d3", "R9 d2 d3"
MOVE_PATTERN = re.compile(
    r'^([RTSP])(\d+)\s+'           # Shape prefix + value
    r'([a-h])(\d{1,2})'           # From position
    r'(?:\s*(?:→|->)\s*|\s+)'     # Separator
    r'([a-h])(\d{1,2})$'          # To position
)

# Special action patterns
AMBUSH_PATTERN = re.compile(r'^ambush\s+([a-h])(\d{1,2})$', re.IGNORECASE)
ASSAULT_PATTERN = re.compile(
    r'^assault\s+([RTSP])(\d+)\s+([a-h])(\d{1,2})'
    r'(?:\s*(?:→|->)\s*|\s+)'
    r'([a-h])(\d{1,2})$',
    re.IGNORECASE
)
SIEGE_PATTERN = re.compile(r'^siege\s+([a-h])(\d{1,2})$', re.IGNORECASE)


@dataclass
class ParsedMove:
    """Result of parsing a move notation string."""
    kind: str  # "move", "ambush", "assault", "siege"
    # For "move" and "assault":
    shape: Optional[Shape] = None
    value: Optional[int] = None
    from_col: Optional[int] = None
    from_row: Optional[int] = None
    to_col: Optional[int] = None
    to_row: Optional[int] = None
    # For "ambush" and "siege":
    target_col: Optional[int] = None
    target_row: Optional[int] = None


def _col_to_index(letter: str) -> int:
    return ord(letter.lower()) - ord('a')


def parse_notation(notation: str) -> ParsedMove:
    """Parse a move notation string into a ParsedMove.

    Raises ValueError if the notation is invalid.
    """
    notation = notation.strip()

    # Try standard move: "R9 d2→d3"
    m = MOVE_PATTERN.match(notation)
    if m:
        return ParsedMove(
            kind="move",
            shape=SHAPE_PREFIXES[m.group(1)],
            value=int(m.group(2)),
            from_col=_col_to_index(m.group(3)),
            from_row=int(m.group(4)),
            to_col=_col_to_index(m.group(5)),
            to_row=int(m.group(6)),
        )

    # Try ambush: "ambush e5"
    m = AMBUSH_PATTERN.match(notation)
    if m:
        return ParsedMove(
            kind="ambush",
            target_col=_col_to_index(m.group(1)),
            target_row=int(m.group(2)),
        )

    # Try assault: "assault T36 d3→e5"
    m = ASSAULT_PATTERN.match(notation)
    if m:
        return ParsedMove(
            kind="assault",
            shape=SHAPE_PREFIXES[m.group(1).upper()],
            value=int(m.group(2)),
            from_col=_col_to_index(m.group(3)),
            from_row=int(m.group(4)),
            target_col=_col_to_index(m.group(5)),
            target_row=int(m.group(6)),
        )

    # Try siege: "siege e5"
    m = SIEGE_PATTERN.match(notation)
    if m:
        return ParsedMove(
            kind="siege",
            target_col=_col_to_index(m.group(1)),
            target_row=int(m.group(2)),
        )

    raise ValueError(f"Invalid notation: '{notation}'")


def resolve_piece(state: GameState, parsed: ParsedMove) -> Piece:
    """Find the piece referenced by a parsed move.

    Matches by shape, value, and position. Raises ValueError if not found.
    """
    if parsed.from_col is None or parsed.from_row is None:
        raise ValueError("Move notation must include source position")
    if parsed.shape is None or parsed.value is None:
        raise ValueError("Move notation must include piece shape and value")

    piece = state.piece_at(parsed.from_row, parsed.from_col)
    if piece is None:
        pos = f"{chr(ord('a') + parsed.from_col)}{parsed.from_row}"
        raise ValueError(f"No piece at {pos}")
    if piece.shape != parsed.shape:
        raise ValueError(
            f"Piece at {piece.position_str} is {piece.shape.name}, "
            f"not {parsed.shape.name}"
        )
    if piece.value != parsed.value:
        raise ValueError(
            f"Piece at {piece.position_str} has value {piece.value}, "
            f"not {parsed.value}"
        )
    return piece


def format_move(piece: Piece, to_row: int, to_col: int) -> str:
    """Format a move as algebraic notation."""
    to_pos = f"{chr(ord('a') + to_col)}{to_row}"
    return f"{piece.notation_prefix}{piece.value} {piece.position_str}→{to_pos}"
