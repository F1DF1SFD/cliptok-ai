"""Fonts and sticker assets available to the editor."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..services.overlay import available_fonts, sticker_ids, sticker_path

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/stickers")
def list_stickers() -> dict:
    return {
        "stickers": [
            {"id": sticker_id, "url": f"/api/stickers/{sticker_id}.png"}
            for sticker_id in sticker_ids()
        ]
    }


@router.get("/stickers/{sticker_id}.png")
def get_sticker(sticker_id: str) -> FileResponse:
    path = sticker_path(sticker_id)
    if not path:
        raise HTTPException(status_code=404, detail="Sticker not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/fonts")
def list_fonts() -> dict:
    return {"fonts": available_fonts()}
