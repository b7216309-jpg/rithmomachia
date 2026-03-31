"""Tests for the game orchestrator — full game flow."""

import pytest
from engine.models import Color, Shape, Piece, GameState, GameStatus, CaptureType
from engine.game import Game


class TestNewGame:
    def test_starts_with_white(self):
        game = Game.new()
        assert game.state.current_player == Color.WHITE

    def test_starts_active(self):
        game = Game.new()
        assert game.state.status == GameStatus.ACTIVE

    def test_starts_turn_1(self):
        game = Game.new()
        assert game.state.turn == 1

    def test_has_legal_moves(self):
        game = Game.new()
        moves = game.get_legal_moves()
        assert len(moves) > 0


class TestStandardMove:
    def test_valid_move(self):
        """Move a white round piece one square forward."""
        game = Game.new()
        # ○2(a1) can move to a2? No, a2 has ○3. Can move to b1? No, b1 has ○4.
        # Let's find a piece that can actually move.
        # ○1(a3) can move to a4 (empty).
        result = game.submit_move("R1 a3→a4")
        assert result.success, result.error
        assert game.state.current_player == Color.BLACK

    def test_wrong_turn(self):
        """Black can't move on White's turn."""
        game = Game.new()
        result = game.submit_move("R3 a16→a15")
        assert not result.success
        # Black piece on white's turn — should fail with "Not your piece"

    def test_invalid_notation(self):
        game = Game.new()
        result = game.submit_move("garbage")
        assert not result.success

    def test_piece_not_found(self):
        game = Game.new()
        result = game.submit_move("R99 a5→a6")
        assert not result.success

    def test_illegal_destination(self):
        """Can't move to a square that's not a legal destination."""
        game = Game.new()
        # ○1(a3) can't jump to a6 (round moves 1 square)
        result = game.submit_move("R1 a3→a6")
        assert not result.success

    def test_turn_alternates(self):
        game = Game.new()
        assert game.state.current_player == Color.WHITE

        result = game.submit_move("R1 a3→a4")
        assert result.success
        assert game.state.current_player == Color.BLACK

        # Black moves: ●2(a14) can move to a13
        result = game.submit_move("R2 a14→a13")
        assert result.success
        assert game.state.current_player == Color.WHITE

    def test_piece_position_updated(self):
        game = Game.new()
        piece_before = game.state.piece_at(3, 0)  # a3 = ○1
        assert piece_before is not None
        assert piece_before.value == 1

        game.submit_move("R1 a3→a4")

        assert game.state.piece_at(3, 0) is None  # a3 now empty
        piece_after = game.state.piece_at(4, 0)    # a4 has the piece
        assert piece_after is not None
        assert piece_after.value == 1

    def test_move_history_recorded(self):
        game = Game.new()
        game.submit_move("R1 a3→a4")
        assert len(game.state.move_history) == 1


class TestEncounterCapture:
    def test_encounter_capture_in_game(self):
        """Set up a position where encounter capture is possible."""
        # Create a minimal board with a white and black piece of equal value
        white = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                      value=5, row=5, col=3)
        black = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                      value=5, row=6, col=3)
        state = GameState(pieces=[white, black])
        game = Game(state)

        result = game.submit_move("R5 d5→d6")
        assert result.success
        assert len(result.captures) == 1
        assert result.captures[0].capture_type == CaptureType.ENCOUNTER
        assert result.captures[0].captured_value == 5

        # Black piece should be captured
        bp = game.state.piece_by_id(2)
        assert bp.captured


class TestAssaultCapture:
    def test_assault_in_game(self):
        """T36 assaults ■72 at distance 2: 36 × 2 = 72."""
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                         value=36, row=3, col=3)
        target = Piece(id=2, color=Color.BLACK, shape=Shape.SQUARE,
                       value=72, row=5, col=3)
        state = GameState(pieces=[attacker, target])
        game = Game(state)

        result = game.submit_move("assault T36 d3→d5")
        assert result.success, result.error
        assert len(result.captures) == 1
        assert result.captures[0].capture_type == CaptureType.ASSAULT

        # Target should be captured
        t = game.state.piece_by_id(2)
        assert t.captured

    def test_invalid_assault(self):
        """Assault with wrong math should fail."""
        attacker = Piece(id=1, color=Color.WHITE, shape=Shape.TRIANGLE,
                         value=7, row=3, col=3)
        target = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                       value=10, row=5, col=3)
        state = GameState(pieces=[attacker, target])
        game = Game(state)

        result = game.submit_move("assault T7 d3→d5")
        assert not result.success


class TestAmbushCapture:
    def test_ambush_in_game(self):
        """Two white pieces sum to black's value: 3 + 5 = 8."""
        f1 = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                   value=3, row=5, col=3)
        f2 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=5, row=5, col=5)
        enemy = Piece(id=3, color=Color.BLACK, shape=Shape.ROUND,
                      value=8, row=5, col=4)
        state = GameState(pieces=[f1, f2, enemy])
        game = Game(state)

        result = game.submit_move("ambush e5")
        assert result.success, result.error
        assert len(result.captures) == 1
        assert result.captures[0].capture_type == CaptureType.AMBUSH

        # Enemy should be captured
        e = game.state.piece_by_id(3)
        assert e.captured

    def test_invalid_ambush(self):
        """Ambush where sum doesn't match."""
        f1 = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                   value=3, row=5, col=3)
        f2 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=5, row=5, col=5)
        enemy = Piece(id=3, color=Color.BLACK, shape=Shape.ROUND,
                      value=10, row=5, col=4)
        state = GameState(pieces=[f1, f2, enemy])
        game = Game(state)

        result = game.submit_move("ambush e5")
        assert not result.success


class TestSiegeCapture:
    def test_siege_in_game(self):
        """Enemy surrounded by 4 white pieces."""
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
        state = GameState(pieces=[enemy, w1, w2, w3, w4])
        game = Game(state)

        result = game.submit_move("siege d8")
        assert result.success, result.error
        assert len(result.captures) == 1
        assert result.captures[0].capture_type == CaptureType.SIEGE

    def test_invalid_siege(self):
        """Enemy not fully surrounded."""
        enemy = Piece(id=1, color=Color.BLACK, shape=Shape.ROUND,
                      value=5, row=8, col=3)
        w1 = Piece(id=2, color=Color.WHITE, shape=Shape.ROUND,
                   value=1, row=7, col=3)
        state = GameState(pieces=[enemy, w1])
        game = Game(state)

        result = game.submit_move("siege d8")
        assert not result.success


class TestVictory:
    def test_victory_by_progression(self):
        """White captures pieces with values 4, 8, 12 → AP → victory."""
        # Pre-captured black pieces
        b1 = Piece(id=10, color=Color.BLACK, shape=Shape.ROUND,
                    value=4, row=0, col=0, captured=True)
        b2 = Piece(id=11, color=Color.BLACK, shape=Shape.ROUND,
                    value=8, row=0, col=0, captured=True)
        # White piece about to capture black piece with value 12
        white = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                      value=12, row=5, col=3)
        target = Piece(id=12, color=Color.BLACK, shape=Shape.TRIANGLE,
                       value=12, row=6, col=3)

        state = GameState(pieces=[white, target, b1, b2])
        game = Game(state)

        result = game.submit_move("R12 d5→d6")
        assert result.success
        assert result.victory is not None
        assert len(result.victory) > 0
        assert game.state.status == GameStatus.WHITE_WINS


class TestDraw:
    def test_draw_after_50_turns_no_capture(self):
        """Draw counter increments and triggers at 50."""
        white = Piece(id=1, color=Color.WHITE, shape=Shape.ROUND,
                      value=1, row=5, col=3)
        black = Piece(id=2, color=Color.BLACK, shape=Shape.ROUND,
                      value=2, row=12, col=3)
        state = GameState(pieces=[white, black])
        state.draw_counter = 49  # One more turn without capture = draw
        game = Game(state)

        result = game.submit_move("R1 d5→d6")
        assert result.success
        assert game.state.status == GameStatus.DRAW


class TestResign:
    def test_white_resigns(self):
        game = Game.new()
        result = game.resign(Color.WHITE)
        assert result.success
        assert game.state.status == GameStatus.BLACK_WINS

    def test_black_resigns(self):
        game = Game.new()
        result = game.resign(Color.BLACK)
        assert result.success
        assert game.state.status == GameStatus.WHITE_WINS

    def test_resign_inactive_game(self):
        game = Game.new()
        game.state.status = GameStatus.DRAW
        result = game.resign(Color.WHITE)
        assert not result.success
