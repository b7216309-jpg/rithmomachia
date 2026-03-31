"""Data models for Rithmomachia game engine.

All game state is represented by immutable dataclasses.
The engine operates on these models — no web dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Color(Enum):
    WHITE = "white"
    BLACK = "black"

    @property
    def opposite(self) -> Color:
        return Color.BLACK if self == Color.WHITE else Color.WHITE


class Shape(Enum):
    ROUND = "round"      # Move range: 1
    TRIANGLE = "triangle"  # Move range: 2
    SQUARE = "square"    # Move range: 3
    PYRAMID = "pyramid"  # Move range: variable (Phase 4)

    @property
    def move_range(self) -> int:
        """Maximum squares this shape can move in one turn."""
        return {
            Shape.ROUND: 1,
            Shape.TRIANGLE: 2,
            Shape.SQUARE: 3,
            Shape.PYRAMID: 3,  # placeholder — uses component ranges in Phase 4
        }[self]

    @property
    def symbol(self) -> dict[Color, str]:
        """Unicode symbols for display."""
        return {
            Shape.ROUND: {Color.WHITE: "○", Color.BLACK: "●"},
            Shape.TRIANGLE: {Color.WHITE: "△", Color.BLACK: "▲"},
            Shape.SQUARE: {Color.WHITE: "□", Color.BLACK: "■"},
            Shape.PYRAMID: {Color.WHITE: "⬡", Color.BLACK: "⬢"},
        }[self]


class CaptureType(Enum):
    ENCOUNTER = "encounter"  # Equal value, move onto
    AMBUSH = "ambush"        # Sum of friendly pieces = target value
    ASSAULT = "assault"      # Value × distance = other value
    SIEGE = "siege"          # Target has no legal moves


class ProgressionType(Enum):
    ARITHMETIC = "arithmetic"
    GEOMETRIC = "geometric"
    HARMONIC = "harmonic"


class GameStatus(Enum):
    ACTIVE = "active"
    WHITE_WINS = "white_wins"
    BLACK_WINS = "black_wins"
    DRAW = "draw"


@dataclass(frozen=True)
class Piece:
    """A single game piece on the board.

    For pyramids, `components` holds (shape, value) tuples for each layer.
    The pyramid's `value` is the sum of component values.
    It can move using any component's move range.
    """
    id: int
    color: Color
    shape: Shape
    value: int
    row: int          # 1-16 (1 = white's back row, 16 = black's back row)
    col: int          # 0-7 (a=0, b=1, ..., h=7)
    captured: bool = False
    components: tuple[tuple[str, int], ...] = ()  # For pyramids: (("round", val), ("triangle", val), ("square", val))

    @property
    def notation_prefix(self) -> str:
        """Shape prefix for algebraic notation: R=round, T=triangle, S=square, P=pyramid."""
        return {
            Shape.ROUND: "R",
            Shape.TRIANGLE: "T",
            Shape.SQUARE: "S",
            Shape.PYRAMID: "P",
        }[self.shape]

    @property
    def symbol(self) -> str:
        """Unicode symbol for this piece."""
        return self.shape.symbol[self.color]

    @property
    def col_letter(self) -> str:
        """Column as a letter (a-h)."""
        return chr(ord('a') + self.col)

    @property
    def position_str(self) -> str:
        """Position in algebraic notation, e.g., 'd2'."""
        return f"{self.col_letter}{self.row}"

    @property
    def label(self) -> str:
        """Full label, e.g., '○9(d2)'."""
        return f"{self.symbol}{self.value}({self.position_str})"

    @property
    def move_ranges(self) -> list[int]:
        """All valid move ranges for this piece. Pyramids have multiple."""
        if self.shape == Shape.PYRAMID and self.components:
            ranges = set()
            for comp_shape, _ in self.components:
                s = Shape(comp_shape)
                ranges.add(s.move_range)
            return sorted(ranges)
        return [self.shape.move_range]

    def moved_to(self, row: int, col: int) -> Piece:
        """Return a new Piece at the given position."""
        return Piece(
            id=self.id, color=self.color, shape=self.shape,
            value=self.value, row=row, col=col, captured=self.captured,
            components=self.components,
        )

    def as_captured(self) -> Piece:
        """Return a new Piece marked as captured."""
        return Piece(
            id=self.id, color=self.color, shape=self.shape,
            value=self.value, row=self.row, col=self.col, captured=True,
            components=self.components,
        )


@dataclass(frozen=True)
class Move:
    """A move: piece moves from (from_row, from_col) to (to_row, to_col)."""
    piece_id: int
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    capture: Optional[Capture] = None

    @property
    def notation(self) -> str:
        """Human-readable notation. Set by the notation module."""
        from_pos = f"{chr(ord('a') + self.from_col)}{self.from_row}"
        to_pos = f"{chr(ord('a') + self.to_col)}{self.to_row}"
        return f"{from_pos}→{to_pos}"


@dataclass(frozen=True)
class Capture:
    """A capture event."""
    capture_type: CaptureType
    captured_piece_id: int
    captured_value: int
    capturing_piece_ids: list[int] = field(default_factory=list)
    description: str = ""  # e.g., "3 + 5 = 8" or "36 × 2 = 72"


@dataclass(frozen=True)
class Progression:
    """A detected mathematical progression among captured values."""
    progression_type: ProgressionType
    values: tuple[int, ...]  # The values forming the progression

    @property
    def description(self) -> str:
        vals = ", ".join(str(v) for v in self.values)
        return f"{self.progression_type.value}({vals})"


@dataclass
class GameState:
    """Complete game state. This is the only mutable model — updated each turn."""
    pieces: list[Piece]
    current_player: Color = Color.WHITE
    turn: int = 1
    status: GameStatus = GameStatus.ACTIVE
    move_history: list[Move] = field(default_factory=list)
    draw_counter: int = 0  # Turns without capture; draw at 50

    @property
    def active_pieces(self) -> list[Piece]:
        """All pieces still on the board."""
        return [p for p in self.pieces if not p.captured]

    def pieces_by_color(self, color: Color) -> list[Piece]:
        """Active pieces for a given color."""
        return [p for p in self.active_pieces if p.color == color]

    def captured_by(self, color: Color) -> list[Piece]:
        """Pieces captured by the given color (i.e., enemy pieces that are captured)."""
        return [p for p in self.pieces if p.captured and p.color == color.opposite]

    def captured_values(self, color: Color) -> list[int]:
        """Values of pieces captured by the given color."""
        return [p.value for p in self.captured_by(color)]

    def piece_at(self, row: int, col: int) -> Optional[Piece]:
        """Get the active piece at a position, or None."""
        for p in self.active_pieces:
            if p.row == row and p.col == col:
                return p
        return None

    def piece_by_id(self, piece_id: int) -> Optional[Piece]:
        """Get a piece by ID (even if captured)."""
        for p in self.pieces:
            if p.id == piece_id:
                return p
        return None

    def update_piece(self, old_piece: Piece, new_piece: Piece) -> None:
        """Replace a piece in the pieces list."""
        for i, p in enumerate(self.pieces):
            if p.id == old_piece.id:
                self.pieces[i] = new_piece
                return
        raise ValueError(f"Piece {old_piece.id} not found in state")
