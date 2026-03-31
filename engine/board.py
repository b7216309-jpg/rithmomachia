"""Board setup and movement logic for Rithmomachia.

Handles initial piece placement, legal move generation,
and path obstruction checking. No capture logic here — that's in captures.py.
"""

from __future__ import annotations

from engine.models import Color, Shape, Piece, Move, GameState


# Board dimensions
COLS = 8   # a-h (0-7)
ROWS = 16  # 1-16

# Initial piece positions: (col_letter, row, shape, value)
# Based on Fulke 1563 ruleset as documented in CLAUDE.md
WHITE_SETUP: list[tuple[str, int, Shape, int]] = [
    # Row 1
    ("a", 1, Shape.ROUND, 2),
    ("b", 1, Shape.ROUND, 4),
    ("c", 1, Shape.ROUND, 6),
    ("d", 1, Shape.ROUND, 8),
    ("e", 1, Shape.TRIANGLE, 10),
    ("f", 1, Shape.TRIANGLE, 12),
    ("g", 1, Shape.SQUARE, 14),
    ("h", 1, Shape.SQUARE, 16),
    # Row 2
    ("a", 2, Shape.ROUND, 3),
    ("b", 2, Shape.ROUND, 5),
    ("c", 2, Shape.ROUND, 7),
    ("d", 2, Shape.ROUND, 9),
    ("e", 2, Shape.TRIANGLE, 15),
    ("f", 2, Shape.TRIANGLE, 25),
    ("g", 2, Shape.SQUARE, 45),
    ("h", 2, Shape.SQUARE, 81),
    # Row 3
    ("a", 3, Shape.ROUND, 1),
    ("b", 3, Shape.TRIANGLE, 9),
    ("c", 3, Shape.SQUARE, 16),
    ("d", 3, Shape.TRIANGLE, 36),
    ("e", 3, Shape.SQUARE, 49),
    ("f", 3, Shape.SQUARE, 64),
    ("g", 3, Shape.TRIANGLE, 25),
    ("h", 3, Shape.ROUND, 1),
]

BLACK_SETUP: list[tuple[str, int, Shape, int]] = [
    # Row 16
    ("a", 16, Shape.ROUND, 3),
    ("b", 16, Shape.ROUND, 5),
    ("c", 16, Shape.ROUND, 7),
    ("d", 16, Shape.ROUND, 9),
    ("e", 16, Shape.TRIANGLE, 11),
    ("f", 16, Shape.TRIANGLE, 13),
    ("g", 16, Shape.SQUARE, 15),
    ("h", 16, Shape.SQUARE, 17),
    # Row 15
    ("a", 15, Shape.ROUND, 4),
    ("b", 15, Shape.ROUND, 6),
    ("c", 15, Shape.ROUND, 8),
    ("d", 15, Shape.ROUND, 10),
    ("e", 15, Shape.TRIANGLE, 20),
    ("f", 15, Shape.TRIANGLE, 30),
    ("g", 15, Shape.SQUARE, 49),
    ("h", 15, Shape.SQUARE, 64),
    # Row 14
    ("a", 14, Shape.ROUND, 2),
    ("b", 14, Shape.TRIANGLE, 16),
    ("c", 14, Shape.SQUARE, 25),
    ("d", 14, Shape.TRIANGLE, 36),
    ("e", 14, Shape.SQUARE, 81),
    ("f", 14, Shape.SQUARE, 72),
    ("g", 14, Shape.TRIANGLE, 42),
    ("h", 14, Shape.ROUND, 2),
]


def _col_index(letter: str) -> int:
    """Convert column letter to 0-based index."""
    return ord(letter.lower()) - ord('a')


def create_initial_pieces() -> list[Piece]:
    """Create all pieces in their starting positions."""
    pieces: list[Piece] = []
    piece_id = 1

    for col_letter, row, shape, value in WHITE_SETUP:
        pieces.append(Piece(
            id=piece_id, color=Color.WHITE, shape=shape,
            value=value, row=row, col=_col_index(col_letter),
        ))
        piece_id += 1

    for col_letter, row, shape, value in BLACK_SETUP:
        pieces.append(Piece(
            id=piece_id, color=Color.BLACK, shape=shape,
            value=value, row=row, col=_col_index(col_letter),
        ))
        piece_id += 1

    return pieces


def create_pyramid(piece_id: int, color: Color, row: int, col: int,
                   components: list[tuple[str, int]]) -> Piece:
    """Create a pyramid piece from component definitions.

    Components are (shape_name, value) tuples, e.g.:
        [("round", 1), ("triangle", 4), ("square", 25)]
    The pyramid's total value is the sum of component values.
    """
    total = sum(v for _, v in components)
    return Piece(
        id=piece_id, color=color, shape=Shape.PYRAMID,
        value=total, row=row, col=col,
        components=tuple(components),
    )


def new_game_state(include_pyramids: bool = False) -> GameState:
    """Create a fresh game state with all pieces in starting positions.

    If include_pyramids is True, adds pyramid pieces for both sides.
    Pyramids are placed at d1 (white, value=91) and e16 (black, value=91).
    Note: this replaces the round pieces at those positions.
    """
    pieces = create_initial_pieces()

    if include_pyramids:
        next_id = max(p.id for p in pieces) + 1

        # White pyramid at d1: replaces ○8(d1)
        # Components: round(1) + triangle(25) + square(64) = 90?
        # Historical: white pyramid = 1+4+9+16+25+36 stacked
        # Simplified: round(4) + triangle(12) + square(25) = 41
        # Let's use a playable set: round(6) + triangle(36) + square(49) = 91
        white_comps = [("round", 6), ("triangle", 36), ("square", 49)]
        pieces = [p for p in pieces if not (p.row == 1 and p.col == 3)]  # Remove ○8(d1)
        pieces.append(create_pyramid(next_id, Color.WHITE, 1, 3, white_comps))
        next_id += 1

        # Black pyramid at e16: replaces ▲11(e16)
        black_comps = [("round", 8), ("triangle", 36), ("square", 49)]
        pieces = [p for p in pieces if not (p.row == 16 and p.col == 4)]  # Remove ▲11(e16)
        pieces.append(create_pyramid(next_id, Color.BLACK, 16, 4, black_comps))

    return GameState(pieces=pieces)


def is_in_bounds(row: int, col: int) -> bool:
    """Check if a position is within the 8×16 board."""
    return 1 <= row <= ROWS and 0 <= col < COLS


def is_path_clear(state: GameState, from_row: int, from_col: int,
                  to_row: int, to_col: int) -> bool:
    """Check that no pieces block the straight orthogonal path between two positions.

    Does NOT check the destination square (that's handled by move/capture logic).
    Only checks intermediate squares along the path.
    """
    dr = 0 if to_row == from_row else (1 if to_row > from_row else -1)
    dc = 0 if to_col == from_col else (1 if to_col > from_col else -1)

    # Must be orthogonal (one of dr/dc must be 0)
    if dr != 0 and dc != 0:
        return False

    r, c = from_row + dr, from_col + dc
    while (r, c) != (to_row, to_col):
        if state.piece_at(r, c) is not None:
            return False
        r += dr
        c += dc

    return True


def legal_moves_for_piece(state: GameState, piece: Piece) -> list[Move]:
    """Generate all legal moves for a single piece.

    A legal move is an orthogonal move of exactly 1..move_range squares
    where the path is clear and the destination is either empty or
    occupied by an enemy of equal value (encounter capture).

    For pyramids: they can move using any component's range (1, 2, or 3).
    Each move uses one range — e.g., a pyramid with round+triangle+square
    can move 1, 2, or 3 squares.
    """
    if piece.captured:
        return []

    moves: list[Move] = []
    max_range = max(piece.move_ranges)

    # Four orthogonal directions: up, down, left, right
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    # For pyramids, valid distances are exactly the component ranges.
    # For normal pieces, valid distances are 1..move_range.
    if piece.shape == Shape.PYRAMID and piece.components:
        valid_distances = set(piece.move_ranges)
    else:
        valid_distances = set(range(1, max_range + 1))

    for dr, dc in directions:
        for dist in range(1, max_range + 1):
            to_row = piece.row + dr * dist
            to_col = piece.col + dc * dist

            if not is_in_bounds(to_row, to_col):
                break  # Off the board — no further moves in this direction

            # Check path is clear up to (but not including) destination
            if not is_path_clear(state, piece.row, piece.col, to_row, to_col):
                break  # Blocked — no further moves in this direction

            # Only generate moves at valid distances
            if dist not in valid_distances:
                # For pyramids, skip this distance but keep checking further
                target = state.piece_at(to_row, to_col)
                if target is not None:
                    break  # Can't go past any piece
                continue

            target = state.piece_at(to_row, to_col)

            if target is None:
                # Empty square — valid move
                moves.append(Move(
                    piece_id=piece.id,
                    from_row=piece.row, from_col=piece.col,
                    to_row=to_row, to_col=to_col,
                ))
            elif target.color == piece.color:
                # Friendly piece — can't land here or go further
                break
            else:
                # Enemy piece — can only land here via capture (encounter).
                # For pyramids, use the total value for encounter.
                if target.value == piece.value:
                    moves.append(Move(
                        piece_id=piece.id,
                        from_row=piece.row, from_col=piece.col,
                        to_row=to_row, to_col=to_col,
                    ))
                # Enemy piece blocks further movement regardless
                break

    return moves


def all_legal_moves(state: GameState, color: Color) -> list[Move]:
    """Generate all legal moves for a player."""
    moves: list[Move] = []
    for piece in state.pieces_by_color(color):
        moves.extend(legal_moves_for_piece(state, piece))
    return moves
