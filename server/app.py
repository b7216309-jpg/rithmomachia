"""FastAPI application for the Rithmomachia game server."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.routes import router

app = FastAPI(title="Rithmomachia", version="0.1.0")

import os
_origins = os.environ.get("CORS_ORIGINS", "*")
_origin_list = [o.strip() for o in _origins.split(",")] if _origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve static files from web/ directory
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(WEB_DIR / "index.html"))
