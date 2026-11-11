"""
Application Branding Service for TAMS.

Manages user-customizable application name, in-app logo, and window/taskbar icon
storage, validation, and resolution.
"""

from __future__ import annotations

import base64
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

import app.database.connection as conn
from app.services.messaging_service import ensure_messaging_seed_data, get_messaging_config
from app.ui.theme import get_app_icon_path

logger = logging.getLogger("TAMS.BrandingService")

DEFAULT_APP_NAME = "TAMS"
SUPPORTED_IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".png",
    ".jpg",
    ".jpeg",
    ".ico",
    ".svg",
    ".bmp",
    ".webp",
})

_MIME_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".gif": "image/gif",
}


def get_branding_dir() -> Path:
    """Returns and ensures the persistent directory for custom branding assets."""
    branding_dir = Path(conn.DATA_DIR) / "branding"
    branding_dir.mkdir(parents=True, exist_ok=True)
    return branding_dir


def clear_branding_images(kind: str) -> None:
    """Removes previously persisted custom branding files of the given kind ('logo' or 'icon')."""
    if kind not in ("logo", "icon"):
        return
    branding_dir = get_branding_dir()
    for path in branding_dir.glob(f"custom_{kind}_*"):
        try:
            if path.is_file():
                path.unlink()
        except Exception as exc:
            logger.debug("Could not remove old branding asset %s: %s", path, exc)


def save_branding_image(source_path: str | Path, kind: str) -> str:
    """
    Validates and copies a user-selected image into persistent app branding storage.

    Args:
        source_path: Path to the chosen image file.
        kind: Either 'logo' or 'icon'.

    Returns:
        Absolute string path to the copied image inside the branding directory.
    """
    if kind not in ("logo", "icon"):
        raise ValueError(f"Invalid branding kind '{kind}'. Expected 'logo' or 'icon'.")

    src = Path(source_path).expanduser().resolve()
    if not src.exists() or not src.is_file():
        raise ValueError(f"Selected image file does not exist: {source_path}")

    ext = src.suffix.lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format '{ext}'. Supported formats: "
            + ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS))
        )

    branding_dir = get_branding_dir().resolve()
    if src.parent == branding_dir and src.name.startswith(f"custom_{kind}_"):
        return str(src)

    clear_branding_images(kind)
    dest = branding_dir / f"custom_{kind}_{uuid.uuid4().hex[:8]}{ext}"
    shutil.copy2(src, dest)
    return str(dest)


def _resolve_custom_asset(configured_path: str | None, fallback: Path) -> tuple[Path, bool]:
    raw = (configured_path or "").strip()
    if raw:
        candidate = Path(raw).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate, True
    return fallback, False


def resolve_app_branding(cfg: dict[str, str] | None = None) -> dict[str, Any]:
    """
    Resolves effective application branding and institute profile details.
    Falls back cleanly to built-in defaults if values are unset or missing on disk.
    """
    if cfg is None:
        try:
            with conn.SessionLocal() as session:
                ensure_messaging_seed_data(session)
                cfg = get_messaging_config(session)
        except Exception as exc:
            logger.debug("Falling back to default branding config: %s", exc)
            cfg = {}

    default_icon = get_app_icon_path()
    logo_path, has_custom_logo = _resolve_custom_asset(cfg.get("app_logo_path"), default_icon)
    icon_path, has_custom_icon = _resolve_custom_asset(cfg.get("app_icon_path"), default_icon)

    app_name = (cfg.get("app_name") or "").strip() or DEFAULT_APP_NAME
    coaching_name = (cfg.get("coaching_name") or "").strip() or app_name

    return {
        "app_name": app_name,
        "coaching_name": coaching_name,
        "coaching_tagline": (cfg.get("coaching_tagline") or "").strip(),
        "coaching_phone": (cfg.get("coaching_phone") or "").strip(),
        "coaching_email": (cfg.get("coaching_email") or "").strip(),
        "coaching_address": (cfg.get("coaching_address") or "").strip(),
        "academic_session": (cfg.get("academic_session") or "").strip(),
        "currency_symbol": (cfg.get("currency_symbol") or "₹").strip() or "₹",
        "logo_path": logo_path,
        "has_custom_logo": has_custom_logo,
        "icon_path": icon_path,
        "has_custom_icon": has_custom_icon,
    }


def image_file_to_data_uri(image_path: str | Path | None, max_bytes: int = 5 * 1024 * 1024) -> str | None:
    """
    Encodes a local image file as a base64 data URI for reliable embedding in
    QTextDocument HTML previews, prints, and PDFs.
    """
    if not image_path:
        return None
    p = Path(image_path)
    if not p.exists() or not p.is_file():
        return None
    try:
        raw = p.read_bytes()
    except OSError:
        return None
    if not raw or len(raw) > max_bytes:
        return None
    mime = _MIME_TYPES.get(p.suffix.lower(), "image/png")
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"
