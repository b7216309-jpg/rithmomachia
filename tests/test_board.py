"""Tests for board setup and movement logic."""

import pytest
from engine.models import Color, Shape, Piece, GameState
from engine.board import (
    create_initial_pieces, new_game_state, is_in_bounds, is_path_clear,
    legal_moves_for_piece, all_legal_moves, ROWS, COLS,
)


class TestInitialSetup:
    def test_piece_count(self):
        pieces = create_initial_pieces()
        white = [p for p in pieces if p.color == Color.WHITE]
        black = [p for p in pieces if p.color == Color.BLACK]
        assert len(white) == 24
        assert len(black) == 24
        assert len(pieces) == 48

    def test_white_occupies_rows_1_to_3(self):
        pieces = create_initial_pieces()
        for p in pieces:
            if p.color == Color.WHITE:
                assert 1 <= p.row <= 3, f"White piece at row {p.row}"

    def test_black_occupies_rows_14_to_16(self):
        pieces = create_initial_pieces()
        for p in pieces:
            if p.color == Color.BLACK:
                assert 14 <= p.row <= 16, f"Black piece at row {p.row}"

    def test_unique_ids(self):
        pieces = create_initial_pieces()
        ids = [p.id for p in pieces]
        assert len(ids) == len(set(ids))

    def test_specific_white_pieces(self):
        """Verify a few key white pieces match CLAUDE.md setup."""
        state = new_game_state()
        # Row 1: ○2(a1)
        p = state.piece_at(1, 0)
        assert p is not None
        assert p.color == Color.WHITE
        assert p.shape == Shape.ROUND
        assert p.value == 2

        # Row 1: □16(h1)
        p = state.piece_at(1, 7)
        assert p.shape == Shape.SQUARE
        assert p.value == 16

        # Row 2: ○9(d2)
        p = state.piece_at(2, 3)
        assert p.shape == Shape.ROUND
        assert p.value == 9

        # Row 3: □64(f3)
        p = state.piece_at(3, 5)
        assert p.shape == Shape.SQUARE
        assert p.value == 64

    def test_specific_black_pieces(self):
        """Verify a few key black pieces match CLAUDE.md setup."""
        state = new_game_state()
        # Row 16: ●9(d16)
        p = state.piece_at(16, 3)
        assert p is not None
        assert p.color == Color.BLACK
        assert p.shape == Shape.ROUND
        assert p.value == 9

        # Row 14: ■81(e14)
        p = state.piece_at(14, 4)
        assert p.shape == Shape.SQUARE
        assert p.value == 81

        # Row 14: ▲42(g14)
        p = state.piece_at(14, 6)
        assert p.shape == Shape.TRIANGLE
        assert p.value == 42


class TestBounds:
    def test_valid_positions(self):
        assert is_in_bounds(1, 0)
        assert is_in_bounds(16, 7)
        assert is_in_bounds(8, 3)

    def test_invalid_positions(self):
        assert not is_in_bounds(0, 0)
        assert not is_in_bounds(17, 0)
        assert not is_in_bounds(1, -1)
        assert not is_in_bounds(1, 8)


class TestPathClear:
    def test_empty_path(self):
        state = GameState(pieces=[])
        assert is_path_clear(state, 5, 3, 5, 7)  # Horizontal
        assert is_path_clear(state, 1, 3, 8, 3)   # Vertical

    def test_blocked_path(self):
        blocker = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                        value=5, row=5, col=4)
        state = GameState(pieces=[blocker])
        # Horizontal, blocker at (5,4) blocks (5,3)->(5,6)
        assert not is_path_clear(state, 5, 3, 5, 6)

    def test_adjacent_move_always_clear(self):
        """A 1-square move has no intermediate squares to block."""
        state = GameState(pieces=[])
        assert is_path_clear(state, 5, 3, 5, 4)
        assert is_path_clear(state, 5, 3, 6, 3)

    def test_diagonal_not_orthogonal(self):
        state = GameState(pieces=[])
        assert not is_path_clear(state, 1, 1, 3, 3)


class TestMovement:
    def test_round_moves_one_square(self):
        """Round pieces move exactly 1 square orthogonally."""
        piece = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                      value=5, row=5, col=3)
        state = GameState(pieces=[piece])
        moves = legal_moves_for_piece(state, piece)
        destinations = {(m.to_row, m.to_col) for m in moves}
        assert destinations == {(6, 3), (4, 3), (5, 4), (5, 2)}

    def test_triangle_moves_up_to_two(self):
        """Triangle pieces move 1 or 2 squares orthogonally."""
        piece = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                      value=9, row=8, col=3)
        state = GameState(pieces=[piece])
        moves = legal_moves_for_piece(state, piece)
        destinations = {(m.to_row, m.to_col) for m in moves}
        expected = {
            (9, 3), (10, 3),   # Up 1, 2
            (7, 3), (6, 3),    # Down 1, 2
            (8, 4), (8, 5),    # Right 1, 2
            (8, 2), (8, 1),    # Left 1, 2
        }
        assert destinations == expected

    def test_square_moves_up_to_three(self):
        """Square pieces move 1, 2, or 3 squares orthogonally."""
        piece = Piece(id=1, color=Color.WHITE, shape=Shape.SQUARE,
                      value=16, row=8, col=3)
        state = GameState(pieces=[piece])
        moves = legal_moves_for_piece(state, piece)
        destinations = {(m.to_row, m.to_col) for m in moves}
        expected = {
            (9, 3), (10, 3), (11, 3),  # Up
            (7, 3), (6, 3), (5, 3),    # Down
            (8, 4), (8, 5), (8, 6),    # Right
            (8, 2), (8, 1), (8, 0),    # Left
        }
        assert destinations == expected

    def test_blocked_by_friendly(self):
        """Pieces can't land on or jump over friendly pieces."""
        piece = Piece(id=1, color=Color.WHITE, shape=Shape.SQUARE,
                      value=16, row=5, col=3)
        blocker = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                        value=1, row=6, col=3)
        state = GameState(pieces=[piece, blocker])
        moves = legal_moves_for_piece(state, piece)
        dests = {(m.to_row, m.to_col) for m in moves}
        # Can't go to (6,3) or beyond in the up direction
        assert (6, 3) not in dests
        assert (7, 3) not in dests

    def test_blocked_by_enemy_no_encounter(self):
        """Can't move onto enemy piece unless values match (encounter)."""
        piece = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                      value=9, row=5, col=3)
        enemy = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                      value=5, row=6, col=3)
        state = GameState(pieces=[piece, enemy])
        moves = legal_moves_for_piece(state, piece)
        dests = {(m.to_row, m.to_col) for m in moves}
        # Can't land on enemy with different value
        assert (6, 3) not in dests
        # Can't jump over enemy
        assert (7, 3) not in dests

    def test_encounter_move_included(self):
        """Can move onto enemy with same value (encounter)."""
        piece = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                      value=5, row=5, col=3)
        enemy = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                      value=5, row=6, col=3)
        state = GameState(pieces=[piece, enemy])
        moves = legal_moves_for_piece(state, piece)
        dests = {(m.to_row, m.to_col) for m in moves}
        assert (6, 3) in dests

    def test_edge_of_board(self):
        """Pieces at the board edge have fewer moves."""
        piece = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                      value=2, row=1, col=0)  # Corner a1
        state = GameState(pieces=[piece])
        moves = legal_moves_for_piece(state, piece)
        dests = {(m.to_row, m.to_col) for m in moves}
        assert dests == {(2, 0), (1, 1)}

    def test_initial_position_white_has_moves(self):
        """White should have legal moves from the starting position."""
        state = new_game_state()
        moves = all_legal_moves(state, Color.WHITE)
        assert len(moves) > 0

    def test_initial_position_all_pieces_present(self):
        """Starting position has all 48 pieces."""
        state = new_game_state()
        assert len(state.active_pieces) == 48

    def test_captured_piece_has_no_moves(self):
        """Captured pieces cannot move."""
        piece = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                      value=5, row=5, col=3, captured=True)
        state = GameState(pieces=[piece])
        moves = legal_moves_for_piece(state, piece)
        assert moves == []
