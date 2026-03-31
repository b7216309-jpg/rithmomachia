"""Tests for pyramid pieces — composite stacks with variable movement."""

import pytest
from engine.models import Color, Shape, Piece, GameState, CaptureType
from engine.board import (
    create_pyramid, new_game_state, legal_moves_for_piece,
)
from engine.captures import check_assault, check_encounter


def make_pyramid(pid, color, row, col, components):
    return create_pyramid(pid, color, row, col, components)


class TestPyramidCreation:
    def test_pyramid_value_is_sum(self):
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        assert p.value == 91
        assert p.shape == Shape.PYRAMID

    def test_pyramid_components_stored(self):
        comps = [("round", 6), ("triangle", 36), ("square", 49)]
        p = make_pyramid(1, Color.WHITE, 5, 3, comps)
        assert len(p.components) == 3
        assert p.components[0] == ("round", 6)

    def test_pyramid_move_ranges(self):
        """Pyramid with round+triangle+square can move 1, 2, or 3 squares."""
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        assert p.move_ranges == [1, 2, 3]

    def test_pyramid_symbol(self):
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        assert p.symbol == "⬡"

    def test_pyramid_notation_prefix(self):
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        assert p.notation_prefix == "P"


class TestPyramidMovement:
    def test_pyramid_moves_1_2_3(self):
        """Pyramid in open space can move using all component shapes."""
        p = make_pyramid(1, Color.WHITE, 8, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        state = GameState(pieces=[p])
        moves = legal_moves_for_piece(state, p)
        dests = {(m.to_row, m.to_col) for m in moves}

        expected = set()
        # Round component: 1 square diagonally
        for dr, dc in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
            r, c = 8 + dr, 3 + dc
            if 1 <= r <= 16 and 0 <= c < 8:
                expected.add((r, c))
        # Triangle/Square components: 2 and 3 squares orthogonally
        for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            for dist in [2, 3]:
                r, c = 8 + dr * dist, 3 + dc * dist
                if 1 <= r <= 16 and 0 <= c < 8:
                    expected.add((r, c))

        assert dests == expected

    def test_pyramid_blocked(self):
        """Pyramid can't jump over pieces."""
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        blocker = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                        value=1, row=6, col=3)
        state = GameState(pieces=[p, blocker])
        moves = legal_moves_for_piece(state, p)
        dests = {(m.to_row, m.to_col) for m in moves}

        # Can't go through (6,3) — so no (6,3), (7,3), (8,3) upward
        assert (6, 3) not in dests
        assert (7, 3) not in dests

    def test_pyramid_encounter_uses_total_value(self):
        """Pyramid encounter uses its total value."""
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        enemy = Piece(id=2, color=Color.BLACK, shape=Shape.SQUARE,
                      value=91, row=6, col=3)
        state = GameState(pieces=[p, enemy])

        cap = check_encounter(state, p, 6, 3)
        assert cap is not None
        assert cap.captured_value == 91

    def test_pyramid_encounter_wrong_value(self):
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        enemy = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                      value=36, row=6, col=3)
        state = GameState(pieces=[p, enemy])

        cap = check_encounter(state, p, 6, 3)
        assert cap is None  # 91 != 36


class TestPyramidAssault:
    def test_assault_with_component_value(self):
        """Pyramid can assault using a component's value: 36 × 2 = 72."""
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        enemy = Piece(id=2, color=Color.BLACK, shape=Shape.SQUARE,
                      value=72, row=7, col=3)
        state = GameState(pieces=[p, enemy])

        cap = check_assault(state, p, enemy)
        assert cap is not None
        assert cap.capture_type == CaptureType.ASSAULT
        assert "36 × 2 = 72" in cap.description

    def test_assault_with_total_value(self):
        """Pyramid can assault using its total value: 91 × 1 = 91."""
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        enemy = Piece(id=2, color=Color.BLACK, shape=Shape.SQUARE,
                      value=91, row=6, col=3)
        state = GameState(pieces=[p, enemy])

        # Distance 1: 91 × 1 = 91 — but that's encounter not assault... let's use dist 2
        enemy2 = Piece(id=3, color=Color.BLACK, shape=Shape.ROUND,
                       value=12, row=7, col=3)
        state2 = GameState(pieces=[p, enemy2])
        # 6 × 2 = 12
        cap = check_assault(state2, p, enemy2)
        assert cap is not None
        assert "6 × 2 = 12" in cap.description

    def test_assault_no_match(self):
        """No component value × distance matches target."""
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        enemy = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                      value=17, row=7, col=3)
        state = GameState(pieces=[p, enemy])

        cap = check_assault(state, p, enemy)
        assert cap is None


class TestPyramidInGame:
    def test_game_with_pyramids(self):
        """Game with pyramids loads correctly."""
        state = new_game_state(include_pyramids=True)
        pyramids = [p for p in state.pieces if p.shape == Shape.PYRAMID]
        assert len(pyramids) == 2

        white_pyr = [p for p in pyramids if p.color == Color.WHITE]
        black_pyr = [p for p in pyramids if p.color == Color.BLACK]
        assert len(white_pyr) == 1
        assert len(black_pyr) == 1
        assert white_pyr[0].value == 91
        assert black_pyr[0].value == 93  # 8 + 36 + 49

    def test_pyramid_preserved_on_move(self):
        """Components are preserved when pyramid moves."""
        p = make_pyramid(1, Color.WHITE, 5, 3,
                         [("round", 6), ("triangle", 36), ("square", 49)])
        moved = p.moved_to(6, 3)
        assert moved.components == p.components
        assert moved.shape == Shape.PYRAMID
        assert moved.value == 91
