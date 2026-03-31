"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# --- Requests ---

class NewGameRequest(BaseModel):
    white: str = Field("human", pattern="^(human|open)$")
    black: str = Field("human", pattern="^(human|open)$")
    white_name: str = "White"
    black_name: str = "Black"
    white_description: str = ""
    black_description: str = ""


class JoinRequest(BaseModel):
    color: str = Field(..., pattern="^(white|black)$")
    name: str = "Player"
    description: str = ""


class MoveRequest(BaseModel):
    aiid: str
    notation: str


class ResignRequest(BaseModel):
    aiid: str


class CommentateJoinRequest(BaseModel):
    name: str = "Commentator"
    description: str = ""


class CommentRequest(BaseModel):
    aiid: str
    message: str


# --- Responses ---

class PieceResponse(BaseModel):
    id: int
    color: str
    shape: str
    value: int
    row: int
    col: int
    captured: bool
    components: list[list] = []  # For pyramids: [[shape, value], ...]


class CaptureResponse(BaseModel):
    capture_type: str
    captured_piece_id: int
    captured_value: int
    capturing_piece_ids: list[int]
    description: str


class MoveResponse(BaseModel):
    notation: str
    piece_id: int
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    capture: Optional[CaptureResponse] = None


class ProgressionResponse(BaseModel):
    type: str
    values: list[int]


class PlayerInfo(BaseModel):
    name: str
    type: str  # "human" or "open"/"agent"
    description: str = ""


class LegalMoveResponse(BaseModel):
    piece_id: int
    piece_label: str
    from_pos: str
    to_pos: str
    to_row: int
    to_col: int
    is_capture: bool = False
    notation: str


class LegalActionsResponse(BaseModel):
    moves: list[LegalMoveResponse]
    assaults: list[CaptureResponse]
    ambushes: list[CaptureResponse]
    sieges: list[CaptureResponse]


class CommentResponse(BaseModel):
    author: str
    message: str
    turn: int
    timestamp: float


class CommentatorInfo(BaseModel):
    name: str
    description: str = ""


class GameStateResponse(BaseModel):
    id: str
    turn: int
    current_player: str
    status: str
    players: dict[str, PlayerInfo]
    board: list[PieceResponse]
    captures: dict[str, list[int]]
    progressions: dict[str, list[ProgressionResponse]]
    last_move: Optional[MoveResponse] = None
    move_count: int
    draw_counter: int
    spectator_count: int = 0
    commentator: Optional[CommentatorInfo] = None


class NewGameResponse(BaseModel):
    id: str
    white_aiid: str
    black_aiid: str


class JoinResponse(BaseModel):
    aiid: str


class MoveResultResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    notation: Optional[str] = None
    captures: list[CaptureResponse] = []
    victory: Optional[list[ProgressionResponse]] = None
    victory_type: str = "none"
    state: Optional[GameStateResponse] = None


class HistoryEntry(BaseModel):
    turn: int
    player: str
    notation: str
    capture: Optional[CaptureResponse] = None
