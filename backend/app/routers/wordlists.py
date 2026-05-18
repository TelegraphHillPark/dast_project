from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.uuid7 import uuid7_str
from app.database import get_db
from app.models.user import User
from app.models.wordlist import Wordlist

router = APIRouter(prefix="/api/wordlists", tags=["wordlists"])

_ALLOWED_TYPES = {"text/plain"}
_SAFE_NAME = re.compile(r"[^\w\-.]")


def _sanitize(name: str) -> str:
    return _SAFE_NAME.sub("_", name)[:200]


@router.post("", status_code=201)
async def upload_wordlist(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a custom payload wordlist (.txt).

    Returns 415 if the file is not plain text.
    Returns 413 if the file exceeds MAX_UPLOAD_SIZE_BYTES (1 GB by default).
    Streams the file to disk to support files up to 1 GB without loading into memory.
    """
    # 415 — type check
    is_txt = (
        file.content_type in _ALLOWED_TYPES
        or (file.filename or "").lower().endswith(".txt")
    )
    if not is_txt:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only plain-text (.txt) wordlist files are accepted",
        )

    os.makedirs(settings.WORDLISTS_DIR, exist_ok=True)

    safe_name = _sanitize(file.filename or "wordlist.txt")
    file_id = uuid7_str()
    dest_path = os.path.join(settings.WORDLISTS_DIR, f"{file_id}_{safe_name}")

    max_size = settings.MAX_UPLOAD_SIZE_BYTES
    chunk_size = 1 * 1024 * 1024  # 1 MB chunks — keeps memory flat for 1 GB files
    total = 0

    try:
        with open(dest_path, "wb") as out:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                # 413 — size check (streaming, no full load into memory)
                if total > max_size:
                    out.close()
                    os.remove(dest_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {max_size // (1024 ** 3)} GB size limit",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    wordlist = Wordlist(
        id=file_id,
        owner_id=current_user.id,
        name=file.filename or safe_name,
        file_path=dest_path,
        size_bytes=total,
        is_builtin=False,
    )
    db.add(wordlist)
    await db.commit()
    await db.refresh(wordlist)

    return {
        "id": wordlist.id,
        "name": wordlist.name,
        "size_bytes": wordlist.size_bytes,
        "created_at": wordlist.created_at.isoformat(),
    }


@router.get("")
async def list_wordlists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List wordlists owned by the current user plus built-in ones."""
    result = await db.execute(
        select(Wordlist)
        .where((Wordlist.owner_id == current_user.id) | (Wordlist.is_builtin == True))
        .order_by(Wordlist.created_at.desc())
    )
    wordlists = result.scalars().all()
    return [
        {
            "id": w.id,
            "name": w.name,
            "size_bytes": w.size_bytes,
            "is_builtin": w.is_builtin,
            "created_at": w.created_at.isoformat(),
        }
        for w in wordlists
    ]


@router.delete("/{wordlist_id}", status_code=204)
async def delete_wordlist(
    wordlist_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user-owned wordlist."""
    result = await db.execute(
        select(Wordlist).where(
            Wordlist.id == wordlist_id,
            Wordlist.owner_id == current_user.id,
            Wordlist.is_builtin == False,
        )
    )
    wordlist = result.scalar_one_or_none()
    if not wordlist:
        raise HTTPException(status_code=404, detail="Wordlist not found")

    if os.path.exists(wordlist.file_path):
        os.remove(wordlist.file_path)

    await db.delete(wordlist)
    await db.commit()
