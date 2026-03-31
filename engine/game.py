"""Game orchestrator for Rithmomachia.

Ties together board, captures, victory, and notation into a complete game loop.
This is the main entry point for playing the game programmatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.models import (
    Color, Piece, Move, Capture, CaptureType, GameState, GameStatus,
    Progression,
)
from engine.board import (
    new_game_state, all_legal_moves, legal_moves_for_piece, is_in_bounds,
)
from engine.captures import (
    check_encounter, check_ambush, check_assault, check_siege,
    find_assault_targets, find_all_captures_for_move,
)
from engine.victory import check_victory, classify_victory, VictoryType
from engine.notation import (
    parse_notation, resolve_piece, format_move, ParsedMove,
)


DRAW_THRESHOLD = 50  # Turns without capture = draw


@dataclass
class MoveResult:
    """The result of applying a move to the game state."""
    success: bool
    error: Optional[str] = None
    move: Optional[Move] = None
    captures: list[Capture] = field(default_factory=list)
    victory: Optional[list[Progression]] = None
    victory_type: str = VictoryType.NONE
    notation: str = ""
    state: Optional[GameState] = None


class Game:
    """High-level game controller. Wraps GameState with validation and game logic."""

    def __init__(self, state: Optional[GameState] = None):
        self.state = state or new_game_state()

    @classmethod
    def new(cls) -> Game:
        """Create a new game with standard starting position."""
        return cls()

    def get_legal_moves(self, color: Optional[Color] = None) -> list[Move]:
        """Get all legal moves for a color (default: current player)."""
        color = color or self.state.current_player
        return all_legal_moves(self.state, color)

    def get_legal_moves_for_piece(self, piece_id: int) -> list[Move]:
        """Get legal moves for a specific piece."""
        piece = self.state.piece_by_id(piece_id)
        if piece is None or piece.captured:
            return []
        return legal_moves_for_piece(self.state, piece)

    def get_assault_targets(self, color: Optional[Color] = None) -> list[Capture]:
        """Get all possible assault captures for a color."""
        color = color or self.state.current_player
        captures: list[Capture] = []
        for piece in self.state.pieces_by_color(color):
            captures.extend(find_assault_targets(self.state, piece))
        return captures

    def get_ambush_captures(self, color: Optional[Color] = None) -> list[Capture]:
        """Get all possible ambush captures for a color."""
        color = color or self.state.current_player
        return check_ambush(self.state, color)

    def get_siege_captures(self, color: Optional[Color] = None) -> list[Capture]:
        """Get all possible siege captures for a color."""
        color = color or self.state.current_player
        return check_siege(self.state, color)

    def get_all_available_actions(self, color: Optional[Color] = None) -> dict:
        """Get all available actions: moves, assaults, ambushes, sieges."""
        color = color or self.state.current_player
        return {
            "moves": self.get_legal_moves(color),
            "assaults": self.get_assault_targets(color),
            "ambushes": self.get_ambush_captures(color),
            "sieges": self.get_siege_captures(color),
        }

    def submit_move(self, notation: str) -> MoveResult:
        """Submit a move via algebraic notation. Validates and applies it.

        This is the primary interface for playing the game.
        Handles standard moves, assaults, ambushes, and siege declarations.
        """
        if self.state.status != GameStatus.ACTIVE:
            return MoveResult(success=False, error="Game is not active")

        try:
            parsed = parse_notation(notation)
        except ValueError as e:
            return MoveResult(success=False, error=str(e))

        if parsed.kind == "move":
            return self._apply_standard_move(parsed, notation)
        elif parsed.kind == "assault":
            return self._apply_assault(parsed, notation)
        elif parsed.kind == "ambush":
            return self._apply_ambush(parsed, notation)
        elif parsed.kind == "siege":
            return self._apply_siege(parsed, notation)
        else:
            return MoveResult(success=False, error=f"Unknown move kind: {parsed.kind}")

    def _apply_standard_move(self, parsed: ParsedMove, notation: str) -> MoveResult:
        """Apply a standard move (with optional encounter capture)."""
        try:
            piece = resolve_piece(self.state, parsed)
        except ValueError as e:
            return MoveResult(success=False, error=str(e))

        if piece.color != self.state.current_player:
            return MoveResult(success=False, error="Not your piece")

        to_row, to_col = parsed.to_row, parsed.to_col

        # Validate the move is in the legal moves list
        legal = legal_moves_for_piece(self.state, piece)
        matching = [m for m in legal if m.to_row == to_row and m.to_col == to_col]
        if not matching:
            return MoveResult(
                success=False,
                error=f"Illegal move: {piece.label} cannot move to "
                      f"{chr(ord('a') + to_col)}{to_row}",
            )

        all_captures: list[Capture] = []

        # Check encounter capture at destination
        encounter = check_encounter(self.state, piece, to_row, to_col)
        if encounter:
            all_captures.append(encounter)
            # Remove captured piece
            cap_piece = self.state.piece_by_id(encounter.captured_piece_id)
            self.state.update_piece(cap_piece, cap_piece.as_captured())

        # Move the piece
        new_piece = piece.moved_to(to_row, to_col)
        self.state.update_piece(piece, new_piece)

        # Check siege after move
        sieges = check_siege(self.state, self.state.current_player)
        for siege in sieges:
            all_captures.append(siege)
            cap_piece = self.state.piece_by_id(siege.captured_piece_id)
            self.state.update_piece(cap_piece, cap_piece.as_captured())

        # Build Move object
        move = Move(
            piece_id=piece.id,
            from_row=piece.row, from_col=piece.col,
            to_row=to_row, to_col=to_col,
            capture=all_captures[0] if all_captures else None,
        )

        return self._finalize_turn(move, all_captures, notation)

    def _apply_assault(self, parsed: ParsedMove, notation: str) -> MoveResult:
        """Apply an assault capture (piece doesn't move to target's square).

        Assault notation: "assault T36 d3→e5"
        The piece at d3 assaults the enemy at e5, then must also make a regular move.

        For simplicity in Phase 1: assault is declared as a standalone action
        that constitutes the player's turn (the attacker doesn't move).
        """
        try:
            piece = resolve_piece(self.state, parsed)
        except ValueError as e:
            return MoveResult(success=False, error=str(e))

        if piece.color != self.state.current_player:
            return MoveResult(success=False, error="Not your piece")

        target_row, target_col = parsed.target_row, parsed.target_col
        target = self.state.piece_at(target_row, target_col)
        if target is None:
            pos = f"{chr(ord('a') + target_col)}{target_row}"
            return MoveResult(success=False, error=f"No piece at {pos} to assault")

        assault = check_assault(self.state, piece, target)
        if assault is None:
            return MoveResult(
                success=False,
                error=f"No valid assault: {piece.label} → {target.label}",
            )

        # Apply the assault capture
        self.state.update_piece(target, target.as_captured())

        # Assault doesn't move the piece — create a move at same position
        move = Move(
            piece_id=piece.id,
            from_row=piece.row, from_col=piece.col,
            to_row=piece.row, to_col=piece.col,  # Stays in place
            capture=assault,
        )

        return self._finalize_turn(move, [assault], notation)

    def _apply_ambush(self, parsed: ParsedMove, notation: str) -> MoveResult:
        """Apply an ambush capture.

        Ambush notation: "ambush e5"
        Declares that an ambush capture is being made on the piece at e5.
        The engine validates that friendly pieces can reach e5 and their values sum correctly.
        """
        target_row, target_col = parsed.target_row, parsed.target_col
        target = self.state.piece_at(target_row, target_col)
        if target is None:
            pos = f"{chr(ord('a') + target_col)}{target_row}"
            return MoveResult(success=False, error=f"No piece at {pos} to ambush")

        if target.color == self.state.current_player:
            return MoveResult(success=False, error="Cannot ambush your own piece")

        # Find valid ambush combinations targeting this piece
        ambushes = check_ambush(self.state, self.state.current_player)
        matching = [a for a in ambushes if a.captured_piece_id == target.id]

        if not matching:
            return MoveResult(
                success=False,
                error=f"No valid ambush on {target.label}",
            )

        # Use the first valid ambush (smallest combo)
        ambush = matching[0]
        self.state.update_piece(target, target.as_captured())

        move = Move(
            piece_id=ambush.capturing_piece_ids[0],  # Primary piece
            from_row=target_row, from_col=target_col,
            to_row=target_row, to_col=target_col,
            capture=ambush,
        )

        return self._finalize_turn(move, [ambush], notation)

    def _apply_siege(self, parsed: ParsedMove, notation: str) -> MoveResult:
        """Apply a siege capture declaration.

        Siege notation: "siege e5"
        This is a standalone declaration — no piece moves.
        Validated: the target must have no legal moves (fully surrounded).
        """
        target_row, target_col = parsed.target_row, parsed.target_col
        target = self.state.piece_at(target_row, target_col)
        if target is None:
            pos = f"{chr(ord('a') + target_col)}{target_row}"
            return MoveResult(success=False, error=f"No piece at {pos} to besiege")

        if target.color == self.state.current_player:
            return MoveResult(success=False, error="Cannot besiege your own piece")

        sieges = check_siege(self.state, self.state.current_player)
        matching = [s for s in sieges if s.captured_piece_id == target.id]

        if not matching:
            return MoveResult(
                success=False,
                error=f"{target.label} is not under siege",
            )

        siege = matching[0]
        self.state.update_piece(target, target.as_captured())

        move = Move(
            piece_id=siege.capturing_piece_ids[0],
            from_row=target_row, from_col=target_col,
            to_row=target_row, to_col=target_col,
            capture=siege,
        )

        return self._finalize_turn(move, [siege], notation)

    def _finalize_turn(self, move: Move, captures: list[Capture],
                       notation: str) -> MoveResult:
        """End-of-turn bookkeeping: record move, check victory, switch turns."""
        self.state.move_history.append(move)

        # Update draw counter
        if captures:
            self.state.draw_counter = 0
        else:
            self.state.draw_counter += 1

        # Check victory for current player
        victory_progs = None
        victory_type = VictoryType.NONE
        captured_vals = self.state.captured_values(self.state.current_player)
        progs = check_victory(captured_vals)
        if progs:
            victory_progs = progs
            victory_type = classify_victory(progs)
            if self.state.current_player == Color.WHITE:
                self.state.status = GameStatus.WHITE_WINS
            else:
                self.state.status = GameStatus.BLACK_WINS

        # Check draw
        if self.state.draw_counter >= DRAW_THRESHOLD:
            self.state.status = GameStatus.DRAW

        # Switch turns
        self.state.turn += 1
        self.state.current_player = self.state.current_player.opposite

        return MoveResult(
            success=True,
            move=move,
            captures=captures,
            victory=victory_progs,
            victory_type=victory_type,
            notation=notation,
            state=self.state,
        )

    def resign(self, color: Color) -> MoveResult:
        """A player resigns."""
        if self.state.status != GameStatus.ACTIVE:
            return MoveResult(success=False, error="Game is not active")

        if color == Color.WHITE:
            self.state.status = GameStatus.BLACK_WINS
        else:
            self.state.status = GameStatus.WHITE_WINS

        return MoveResult(
            success=True,
            notation=f"{color.value} resigns",
            state=self.state,
        )
