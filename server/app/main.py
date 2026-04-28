from __future__ import annotations

import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DB_PATH, ROOT_DIR

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.routes import browse, dialog, favorites, history, media, player, settings, sources  # noqa: E402
from app.state import dependency_status, initialize  # noqa: E402


app = FastAPI(
    title="StillFrame Local API",
    version="0.1.0",
    description="Local API for the StillFrame Electron media center.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    initialize()


@app.get("/health")
def health() -> dict:
    status = dependency_status()
    return {
        "ok": True,
        "app": "StillFrame",
        "version": "0.1.0",
        "database_path": str(DB_PATH),
        **status,
    }


app.include_router(sources.router)
app.include_router(browse.router)
app.include_router(dialog.router)
app.include_router(media.router)
app.include_router(player.router)
app.include_router(favorites.router)
app.include_router(history.router)
app.include_router(settings.router)
