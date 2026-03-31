"""REST API routes for Rithmomachia game server."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import APIRouter, HTTPException

from engine.models import Color, GameStatus, Capture, Move
from engine.game import Game
from engine.board import all_legal_moves
from engine.captures import check_ambush, find_assault_targets, check_siege
from engine.vision import build_vision
from engine.victory import find_progressions
from engine.notation import format_move
from server.schemas import (
    NewGameRequest, NewGameResponse, JoinRequest, JoinResponse,
    MoveRequest, MoveResultResponse, ResignRequest,
    CommentateJoinRequest, CommentRequest, CommentResponse, CommentatorInfo,
    GameStateResponse, PieceResponse, CaptureResponse, MoveResponse,
    ProgressionResponse, PlayerInfo, LegalMoveResponse, LegalActionsResponse,
    HistoryEntry,
)
from server.db import init_db, save_game_start, save_game_end, list_games, get_game_record

# Initialize DB on import
init_db()

router = APIRouter(prefix="/api/game")


@dataclass
class PlayerSeat:
    name: str
    type: str  # "human" or "open"
    token: str
    description: str = ""


@dataclass
class Commentator:
    name: str
    description: str
    token: str


@dataclass
class StoredComment:
    author: str
    message: str
    turn: int
    timestamp: float


@dataclass
class GameSession:
    id: str
    game: Game
    white: PlayerSeat
    black: PlayerSeat
    move_event: asyncio.Event = field(default_factory=asyncio.Event)
    comment_event: asyncio.Event = field(default_factory=asyncio.Event)
    spectator_count: int = 0
    commentator: Optional[Commentator] = None
    comments: list[StoredComment] = field(default_factory=list)
    votes: dict[str, int] = field(default_factory=lambda: {"white": 0, "black": 0})

    def seat_for_token(self, token: str) -> Optional[Color]:
        if token == self.white.token:
            return Color.WHITE
        if token == self.black.token:
            return Color.BLACK
        return None


# In-memory game store
games: dict[str, GameSession] = {}


def _get_session(game_id: str) -> GameSession:
    session = games.get(game_id)
    if session is None:
        raise HTTPException(404, "Game not found")
    return session


def _piece_response(p) -> PieceResponse:
    return PieceResponse(
        id=p.id, color=p.color.value, shape=p.shape.value,
        value=p.value, row=p.row, col=p.col, captured=p.captured,
        components=[list(c) for c in p.components] if p.components else [],
    )


def _capture_response(c: Capture) -> CaptureResponse:
    return CaptureResponse(
        capture_type=c.capture_type.value,
        captured_piece_id=c.captured_piece_id,
        captured_value=c.captured_value,
        capturing_piece_ids=list(c.capturing_piece_ids),
        description=c.description,
    )


def _move_response(m: Move, notation: str) -> MoveResponse:
    return MoveResponse(
        notation=notation,
        piece_id=m.piece_id,
        from_row=m.from_row, from_col=m.from_col,
        to_row=m.to_row, to_col=m.to_col,
        capture=_capture_response(m.capture) if m.capture else None,
    )


def _state_response(session: GameSession) -> GameStateResponse:
    state = session.game.state
    white_caps = state.captured_values(Color.WHITE)
    black_caps = state.captured_values(Color.BLACK)

    white_progs = find_progressions(white_caps)
    black_progs = find_progressions(black_caps)

    last = None
    if state.move_history:
        last_move = state.move_history[-1]
        last = _move_response(last_move, last_move.notation)

    return GameStateResponse(
        id=session.id,
        turn=state.turn,
        current_player=state.current_player.value,
        status=state.status.value,
        players={
            "white": PlayerInfo(name=session.white.name, type=session.white.type, description=session.white.description),
            "black": PlayerInfo(name=session.black.name, type=session.black.type, description=session.black.description),
        },
        board=[_piece_response(p) for p in state.pieces],
        captures={
            "white": white_caps,
            "black": black_caps,
        },
        progressions={
            "white": [ProgressionResponse(type=p.progression_type.value, values=list(p.values)) for p in white_progs],
            "black": [ProgressionResponse(type=p.progression_type.value, values=list(p.values)) for p in black_progs],
        },
        last_move=last,
        move_count=len(state.move_history),
        draw_counter=state.draw_counter,
        spectator_count=session.spectator_count,
        commentator=CommentatorInfo(name=session.commentator.name, description=session.commentator.description)
            if session.commentator else None,
    )


# --- Endpoints ---

@router.post("/new", response_model=NewGameResponse)
def new_game(req: NewGameRequest):
    game_id = str(uuid.uuid4())[:8]
    white_token = str(uuid.uuid4())[:12]
    black_token = str(uuid.uuid4())[:12]

    session = GameSession(
        id=game_id,
        game=Game.new(),
        white=PlayerSeat(name=req.white_name, type=req.white, token=white_token, description=req.white_description),
        black=PlayerSeat(name=req.black_name, type=req.black, token=black_token, description=req.black_description),
    )
    games[game_id] = session

    save_game_start(game_id, session.white.name, session.black.name,
                    req.white, req.black)

    return NewGameResponse(id=game_id, white_token=white_token, black_token=black_token)


@router.post("/{game_id}/join", response_model=JoinResponse)
def join_game(game_id: str, req: JoinRequest):
    session = _get_session(game_id)
    color = Color(req.color)

    seat = session.white if color == Color.WHITE else session.black
    if seat.type != "open":
        raise HTTPException(400, f"{req.color} seat is not open")

    seat.name = req.name
    seat.type = "agent"
    seat.description = req.description
    return JoinResponse(token=seat.token)


@router.get("/{game_id}/state", response_model=GameStateResponse)
def get_state(game_id: str):
    session = _get_session(game_id)
    return _state_response(session)


@router.get("/{game_id}/legal", response_model=LegalActionsResponse)
def get_legal(game_id: str):
    session = _get_session(game_id)
    state = session.game.state
    color = state.current_player

    # Standard moves
    moves = all_legal_moves(state, color)
    move_responses = []
    for m in moves:
        piece = state.piece_by_id(m.piece_id)
        target = state.piece_at(m.to_row, m.to_col)
        is_cap = target is not None and target.color != piece.color
        notation = format_move(piece, m.to_row, m.to_col)
        move_responses.append(LegalMoveResponse(
            piece_id=m.piece_id,
            piece_label=piece.label,
            from_pos=piece.position_str,
            to_pos=f"{chr(ord('a') + m.to_col)}{m.to_row}",
            to_row=m.to_row,
            to_col=m.to_col,
            is_capture=is_cap,
            notation=notation,
        ))

    # Assaults
    assault_caps = []
    for piece in state.pieces_by_color(color):
        for cap in find_assault_targets(state, piece):
            assault_caps.append(_capture_response(cap))

    # Ambushes
    ambush_caps = [_capture_response(c) for c in check_ambush(state, color)]

    # Sieges
    siege_caps = [_capture_response(c) for c in check_siege(state, color)]

    return LegalActionsResponse(
        moves=move_responses,
        assaults=assault_caps,
        ambushes=ambush_caps,
        sieges=siege_caps,
    )


@router.get("/{game_id}/vision")
def get_vision(game_id: str, color: str = "white"):
    """LLM-optimized board representation (6 layers).

    Returns structured JSON + raw_text field ready for LLM prompts.
    """
    session = _get_session(game_id)
    try:
        c = Color(color)
    except ValueError:
        raise HTTPException(400, f"Invalid color: {color}")
    return build_vision(session.game.state, c)


@router.post("/{game_id}/move", response_model=MoveResultResponse)
def submit_move(game_id: str, req: MoveRequest):
    session = _get_session(game_id)

    # Validate token
    color = session.seat_for_token(req.token)
    if color is None:
        raise HTTPException(403, "Invalid token")
    if color != session.game.state.current_player:
        raise HTTPException(400, "Not your turn")

    result = session.game.submit_move(req.notation)

    if not result.success:
        return MoveResultResponse(success=False, error=result.error)

    # Signal waiting clients
    session.move_event.set()
    session.move_event = asyncio.Event()

    # Persist if game just ended
    if session.game.state.status != GameStatus.ACTIVE:
        _persist_game_end(session)

    resp = MoveResultResponse(
        success=True,
        notation=result.notation,
        captures=[_capture_response(c) for c in result.captures],
        victory=[ProgressionResponse(type=p.progression_type.value, values=list(p.values))
                 for p in result.victory] if result.victory else None,
        victory_type=result.victory_type,
        state=_state_response(session),
    )
    return resp


@router.get("/{game_id}/history")
def get_history(game_id: str):
    session = _get_session(game_id)
    state = session.game.state
    entries = []
    for i, move in enumerate(state.move_history):
        player = "white" if i % 2 == 0 else "black"
        entries.append(HistoryEntry(
            turn=i + 1,
            player=player,
            notation=move.notation,
            capture=_capture_response(move.capture) if move.capture else None,
        ))
    return entries


@router.post("/{game_id}/resign")
def resign(game_id: str, req: ResignRequest):
    session = _get_session(game_id)
    color = session.seat_for_token(req.token)
    if color is None:
        raise HTTPException(403, "Invalid token")

    result = session.game.resign(color)
    if not result.success:
        raise HTTPException(400, result.error)

    session.move_event.set()

    # Persist resign
    _persist_game_end(session)

    return {"success": True, "status": session.game.state.status.value}


@router.post("/{game_id}/commentate")
def join_as_commentator(game_id: str, req: CommentateJoinRequest):
    session = _get_session(game_id)
    if session.commentator is not None:
        raise HTTPException(400, "Commentator slot already taken")
    token = str(uuid.uuid4())[:12]
    session.commentator = Commentator(name=req.name, description=req.description, token=token)
    return {"token": token, "game_id": game_id}


@router.post("/{game_id}/comment")
def post_comment(game_id: str, req: CommentRequest):
    import time
    session = _get_session(game_id)
    if session.commentator is None or req.token != session.commentator.token:
        raise HTTPException(403, "Invalid commentator token")
    comment = StoredComment(
        author=session.commentator.name,
        message=req.message,
        turn=len(session.game.state.move_history),
        timestamp=time.time(),
    )
    session.comments.append(comment)
    # Signal waiting clients
    session.comment_event.set()
    session.comment_event = asyncio.Event()
    return {"success": True, "comment_count": len(session.comments)}


@router.get("/{game_id}/comments")
def get_comments(game_id: str, after: int = 0):
    session = _get_session(game_id)
    comments = session.comments[after:]
    return {
        "comments": [
            CommentResponse(author=c.author, message=c.message, turn=c.turn, timestamp=c.timestamp)
            for c in comments
        ],
        "total": len(session.comments),
    }


@router.get("/{game_id}/comments/wait")
async def wait_for_comment(game_id: str, after: int = 0):
    """Long-poll: blocks until a new comment is posted after the given count."""
    session = _get_session(game_id)
    if len(session.comments) > after:
        comments = session.comments[after:]
        return {
            "comments": [
                CommentResponse(author=c.author, message=c.message, turn=c.turn, timestamp=c.timestamp)
                for c in comments
            ],
            "total": len(session.comments),
        }
    try:
        await asyncio.wait_for(session.comment_event.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        pass
    comments = session.comments[after:]
    return {
        "comments": [
            CommentResponse(author=c.author, message=c.message, turn=c.turn, timestamp=c.timestamp)
            for c in comments
        ],
        "total": len(session.comments),
    }


@router.get("/{game_id}/commentator-context")
def get_commentator_context(game_id: str):
    """Gives the commentator full context: player profiles, game state, last moves."""
    session = _get_session(game_id)
    state = session.game.state
    history = []
    for i, m in enumerate(state.move_history):
        history.append({
            "turn": i + 1,
            "player": "white" if i % 2 == 0 else "black",
            "notation": m.notation,
            "capture": m.capture.description if m.capture else None,
        })
    return {
        "players": {
            "white": {"name": session.white.name, "description": session.white.description, "type": session.white.type},
            "black": {"name": session.black.name, "description": session.black.description, "type": session.black.type},
        },
        "status": state.status.value,
        "current_player": state.current_player.value,
        "move_count": len(state.move_history),
        "captures": {
            "white": state.captured_values(Color.WHITE),
            "black": state.captured_values(Color.BLACK),
        },
        "recent_moves": history[-5:] if history else [],
        "spectator_count": session.spectator_count,
    }


@router.post("/{game_id}/vote")
def cast_vote(game_id: str, color: str = "white"):
    session = _get_session(game_id)
    if color not in ("white", "black"):
        raise HTTPException(400, "color must be 'white' or 'black'")
    session.votes[color] += 1
    total = session.votes["white"] + session.votes["black"]
    return {
        "votes": session.votes,
        "white_pct": round(session.votes["white"] / total * 100) if total else 50,
        "black_pct": round(session.votes["black"] / total * 100) if total else 50,
    }


@router.get("/{game_id}/votes")
def get_votes(game_id: str):
    session = _get_session(game_id)
    total = session.votes["white"] + session.votes["black"]
    return {
        "votes": session.votes,
        "white_pct": round(session.votes["white"] / total * 100) if total else 50,
        "black_pct": round(session.votes["black"] / total * 100) if total else 50,
    }


@router.post("/{game_id}/spectate")
def register_spectator(game_id: str):
    session = _get_session(game_id)
    session.spectator_count += 1
    return {"spectator_count": session.spectator_count}


@router.get("/{game_id}/wait")
async def wait_for_move(game_id: str, after_turn: int = 0):
    """Long-poll: blocks until a new move is made after the given turn number."""
    session = _get_session(game_id)

    if len(session.game.state.move_history) > after_turn:
        return _state_response(session)

    try:
        await asyncio.wait_for(session.move_event.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        pass

    return _state_response(session)


def _persist_game_end(session: GameSession):
    """Save completed game to DB with a short summary."""
    state = session.game.state
    status = state.status.value
    winner = None
    if state.status == GameStatus.WHITE_WINS:
        winner = "white"
    elif state.status == GameStatus.BLACK_WINS:
        winner = "black"

    w_caps = state.captured_values(Color.WHITE)
    b_caps = state.captured_values(Color.BLACK)
    mc = len(state.move_history)

    parts = []
    if winner:
        parts.append(f"{winner.title()} wins")
    elif state.status == GameStatus.DRAW:
        parts.append("Draw")
    parts.append(f"{mc} moves")
    if w_caps:
        parts.append(f"W captured {len(w_caps)} (sum {sum(w_caps)})")
    if b_caps:
        parts.append(f"B captured {len(b_caps)} (sum {sum(b_caps)})")
    summary = " | ".join(parts)

    save_game_end(
        game_id=session.id,
        status=status,
        winner=winner,
        victory_type="none",
        move_count=mc,
        white_captures=w_caps,
        black_captures=b_caps,
        summary=summary,
    )


@router.get("/history/all")
def get_all_history(limit: int = 50, offset: int = 0):
    """Get all completed game records for the profile/history page."""
    return list_games(limit, offset)
