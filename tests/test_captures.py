"""Tests for all four capture types."""

import pytest
from engine.models import Color, Shape, Piece, CaptureType, GameState
from engine.captures import (
    check_encounter, check_assault, check_ambush, check_siege,
    find_assault_targets,
)


def make_state(*pieces: Piece) -> GameState:
    return GameState(pieces=list(pieces))


class TestEncounter:
    def test_equal_value_capture(self):
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                         value=9, row=5, col=3)
        target = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                       value=9, row=6, col=3)
        state = make_state(attacker, target)

        cap = check_encounter(state, attacker, 6, 3)
        assert cap is not None
        assert cap.capture_type == CaptureType.ENCOUNTER
        assert cap.captured_piece_id == 2
        assert cap.captured_value == 9

    def test_different_value_no_capture(self):
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                         value=9, row=5, col=3)
        target = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                       value=5, row=6, col=3)
        state = make_state(attacker, target)

        cap = check_encounter(state, attacker, 6, 3)
        assert cap is None

    def test_friendly_no_capture(self):
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                         value=9, row=5, col=3)
        friend = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                       value=9, row=6, col=3)
        state = make_state(attacker, friend)

        cap = check_encounter(state, attacker, 6, 3)
        assert cap is None

    def test_empty_square_no_capture(self):
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                         value=9, row=5, col=3)
        state = make_state(attacker)

        cap = check_encounter(state, attacker, 6, 3)
        assert cap is None


class TestAssault:
    def test_basic_assault(self):
        """T36 is 2 squares from ■72: 36 × 2 = 72."""
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                         value=36, row=3, col=3)
        target = Piece(id=2, color=Color.BLACK, shape=Shape.SQUARE,
                       value=72, row=5, col=3)
        state = make_state(attacker, target)

        cap = check_assault(state, attacker, target)
        assert cap is not None
        assert cap.capture_type == CaptureType.ASSAULT
        assert cap.captured_piece_id == 2
        assert "36 × 2 = 72" in cap.description

    def test_reverse_assault(self):
        """Target value × distance = attacker value: 8 × 3 = 24."""
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.SQUARE,
                         value=24, row=5, col=3)
        target = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                       value=8, row=5, col=6)
        state = make_state(attacker, target)

        cap = check_assault(state, attacker, target)
        assert cap is not None
        assert "8 × 3 = 24" in cap.description

    def test_assault_blocked_path(self):
        """Assault requires clear line of sight."""
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                         value=36, row=3, col=3)
        blocker = Piece(id=3, color=Color.WHITE, shape=Shape.ROUND,
                        value=1, row=4, col=3)
        target = Piece(id=2, color=Color.BLACK, shape=Shape.SQUARE,
                       value=72, row=5, col=3)
        state = make_state(attacker, blocker, target)

        cap = check_assault(state, attacker, target)
        assert cap is None

    def test_assault_not_orthogonal(self):
        """Assault only works along rows/columns."""
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                         value=36, row=3, col=3)
        target = Piece(id=2, color=Color.BLACK, shape=Shape.SQUARE,
                       value=72, row=5, col=5)
        state = make_state(attacker, target)

        cap = check_assault(state, attacker, target)
        assert cap is None

    def test_assault_wrong_math(self):
        """No valid value × distance relationship."""
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                         value=7, row=3, col=3)
        target = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                       value=10, row=5, col=3)
        state = make_state(attacker, target)

        cap = check_assault(state, attacker, target)
        assert cap is None

    def test_assault_friendly_no_capture(self):
        """Can't assault your own pieces."""
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                         value=36, row=3, col=3)
        friend = Piece(id=2, color=Color.WHITE, shape=Shape.SQUARE,
                       value=72, row=5, col=3)
        state = make_state(attacker, friend)

        cap = check_assault(state, attacker, friend)
        assert cap is None

    def test_find_all_assault_targets(self):
        """find_assault_targets returns all valid assaults for a piece."""
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                         value=6, row=5, col=3)
        target1 = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                        value=12, row=7, col=3)  # 6 × 2 = 12
        target2 = Piece(id=3, color=Color.BLACK, shape=Shape.ROUND,
                        value=18, row=5, col=6)  # 6 × 3 = 18
        state = make_state(attacker, target1, target2)

        caps = find_assault_targets(state, attacker)
        assert len(caps) == 2
        captured_ids = {c.captured_piece_id for c in caps}
        assert captured_ids == {2, 3}


class TestAmbush:
    def test_basic_ambush(self):
        """Two pieces sum to enemy value: 3 + 5 = 8."""
        friend1 = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                        value=3, row=5, col=3)
        friend2 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                        value=5, row=5, col=5)
        enemy = Piece(id=3, color=Color.BLACK, shape=Shape.ROUND,
                      value=8, row=5, col=4)
        state = make_state(friend1, friend2, enemy)

        caps = check_ambush(state, Color.WHITE)
        assert len(caps) >= 1
        cap = caps[0]
        assert cap.capture_type == CaptureType.AMBUSH
        assert cap.captured_piece_id == 3
        assert cap.captured_value == 8

    def test_ambush_must_reach_target(self):
        """Ambushing pieces must be able to reach the target's square."""
        friend1 = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                        value=3, row=5, col=3)
        # Round can only reach 1 square away — enemy at distance 3
        enemy = Piece(id=3, color=Color.BLACK, shape=Shape.ROUND,
                      value=6, row=5, col=6)
        friend2 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                        value=3, row=5, col=5)  # Can reach enemy
        state = make_state(friend1, friend2, enemy)

        caps = check_ambush(state, Color.WHITE)
        # friend1 can't reach enemy (distance 3, round range 1)
        # So only friend2 can reach, but one piece isn't enough for ambush
        matching = [c for c in caps if c.captured_piece_id == 3]
        assert len(matching) == 0

    def test_ambush_three_pieces(self):
        """Three pieces summing to enemy value."""
        f1 = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                   value=2, row=4, col=3)
        f2 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=3, row=5, col=4)
        f3 = Piece(id=3, color=Color.WHITE, shape=Shape.ROUND,
                   value=4, row=6, col=3)
        enemy = Piece(id=4, color=Color.BLACK, shape=Shape.ROUND,
                      value=9, row=5, col=3)
        state = make_state(f1, f2, f3, enemy)

        caps = check_ambush(state, Color.WHITE)
        matching = [c for c in caps if c.captured_piece_id == 4]
        assert len(matching) >= 1
        # The three pieces should sum: 2 + 3 + 4 = 9
        three_piece = [c for c in matching if len(c.capturing_piece_ids) == 3]
        assert len(three_piece) == 1

    def test_no_ambush_wrong_sum(self):
        """Pieces don't sum to enemy value — no ambush."""
        f1 = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                   value=3, row=5, col=3)
        f2 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=5, row=5, col=5)
        enemy = Piece(id=3, color=Color.BLACK, shape=Shape.ROUND,
                      value=10, row=5, col=4)
        state = make_state(f1, f2, enemy)

        caps = check_ambush(state, Color.WHITE)
        matching = [c for c in caps if c.captured_piece_id == 3]
        assert len(matching) == 0


class TestSiege:
    def test_basic_siege(self):
        """Enemy surrounded on all four sides."""
        enemy = Piece(id=1, color=Color.BLACK, shape=Shape.ROUND,
                      value=5, row=8, col=3)
        w1 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=7, col=3)
        w2 = Piece(id=3, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=9, col=3)
        w3 = Piece(id=4, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=8, col=2)
        w4 = Piece(id=5, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=8, col=4)
        state = make_state(enemy, w1, w2, w3, w4)

        caps = check_siege(state, Color.WHITE)
        assert len(caps) == 1
        assert caps[0].captured_piece_id == 1
        assert caps[0].capture_type == CaptureType.SIEGE

    def test_siege_with_board_edge(self):
        """Enemy in corner — 2 edges + 2 pieces = siege."""
        enemy = Piece(id=1, color=Color.BLACK, shape=Shape.ROUND,
                      value=5, row=1, col=0)  # a1 corner
        w1 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=2, col=0)
        w2 = Piece(id=3, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=1, col=1)
        state = make_state(enemy, w1, w2)

        caps = check_siege(state, Color.WHITE)
        assert len(caps) == 1

    def test_no_siege_open_square(self):
        """Enemy has at least one open adjacent square — not sieged."""
        enemy = Piece(id=1, color=Color.BLACK, shape=Shape.ROUND,
                      value=5, row=8, col=3)
        w1 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=7, col=3)
        w2 = Piece(id=3, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=9, col=3)
        w3 = Piece(id=4, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=8, col=2)
        # col+1 is open!
        state = make_state(enemy, w1, w2, w3)

        caps = check_siege(state, Color.WHITE)
        assert len(caps) == 0

    def test_no_siege_friendly_neighbor(self):
        """Enemy surrounded but one neighbor is friendly — not sieged."""
        enemy = Piece(id=1, color=Color.BLACK, shape=Shape.ROUND,
                      value=5, row=8, col=3)
        w1 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=7, col=3)
        w2 = Piece(id=3, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=9, col=3)
        w3 = Piece(id=4, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=8, col=2)
        friend = Piece(id=5, color=Color.BLACK, shape=Shape.ROUND,
                       value=1, row=8, col=4)  # Friendly to enemy
        state = make_state(enemy, w1, w2, w3, friend)

        caps = check_siege(state, Color.WHITE)
        assert len(caps) == 0

    def test_siege_edge_piece(self):
        """Enemy on board edge — needs fewer besieging pieces."""
        enemy = Piece(id=1, color=Color.BLACK, shape=Shape.ROUND,
                      value=5, row=1, col=3)  # Bottom edge
        w1 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=2, col=3)
        w2 = Piece(id=3, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=1, col=2)
        w3 = Piece(id=4, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=1, col=4)
        state = make_state(enemy, w1, w2, w3)

        caps = check_siege(state, Color.WHITE)
        assert len(caps) == 1
