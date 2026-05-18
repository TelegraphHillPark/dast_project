"""
Tests for HTTP 413 (file too large) and 415 (wrong media type) on avatar upload.
Uses TestClient with a mocked authenticated user — no real DB needed.
"""
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AVATAR_URL = "/api/users/me/avatar"
FAKE_USER = MagicMock(spec=User, id="test-user-id", avatar_url=None)


def _auth_override():
    """Replace get_current_user dependency with a fake user."""
    return FAKE_USER


def _db_override():
    """Replace get_db dependency with a no-op async session stub."""
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


# Apply dependency overrides for all tests in this module
@pytest.fixture(autouse=True)
def override_deps():
    from app.core.deps import get_current_user
    from app.database import get_db

    app.dependency_overrides[get_current_user] = _auth_override
    app.dependency_overrides[get_db] = _db_override
    yield
    app.dependency_overrides.clear()


client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# 415 — wrong content type
# ---------------------------------------------------------------------------

def test_415_pdf_file():
    """Uploading a PDF should return 415 Unsupported Media Type."""
    response = client.post(
        AVATAR_URL,
        files={"file": ("document.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    assert response.status_code == 415, response.text


def test_415_text_file():
    """Uploading a plain text file should return 415."""
    response = client.post(
        AVATAR_URL,
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 415, response.text


def test_415_no_content_type():
    """Sending with octet-stream (unknown type) should also return 415."""
    response = client.post(
        AVATAR_URL,
        files={"file": ("blob.bin", b"\x00\x01\x02", "application/octet-stream")},
    )
    assert response.status_code == 415, response.text


# ---------------------------------------------------------------------------
# 413 — file too large (> 5 MB)
# ---------------------------------------------------------------------------

def test_413_oversized_jpeg():
    """A JPEG larger than 5 MB should return 413 Request Entity Too Large."""
    big_file = b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024 + 1)  # 5 MB + 1 byte
    response = client.post(
        AVATAR_URL,
        files={"file": ("big.jpg", big_file, "image/jpeg")},
    )
    assert response.status_code == 413, response.text


def test_413_oversized_png():
    """A PNG over the limit should also return 413."""
    big_file = b"\x89PNG" + b"y" * (6 * 1024 * 1024)  # 6 MB
    response = client.post(
        AVATAR_URL,
        files={"file": ("big.png", big_file, "image/png")},
    )
    assert response.status_code == 413, response.text


# ---------------------------------------------------------------------------
# Happy path — ensure valid small files still work (regression guard)
# ---------------------------------------------------------------------------

def test_valid_jpeg_small():
    """A small valid JPEG should NOT return 413 or 415."""
    with patch("app.services.user.os.makedirs"), \
         patch("builtins.open", MagicMock()), \
         patch("app.services.user.shutil.copyfileobj"):
        response = client.post(
            AVATAR_URL,
            files={"file": ("avatar.jpg", b"\xff\xd8\xff" + b"a" * 100, "image/jpeg")},
        )
    # 200 or any non-413/415 is acceptable here
    assert response.status_code not in (413, 415), response.text
