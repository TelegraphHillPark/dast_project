from fastapi import APIRouter

router = APIRouter(prefix="/api/wordlists", tags=["wordlists"])


@router.post("")
async def upload_wordlist():
    """Stub — будет реализован в Sprint 4."""
    return {"detail": "not implemented"}


@router.get("")
async def list_wordlists():
    """Stub — будет реализован в Sprint 4."""
    return {"detail": "not implemented"}
