"""
TAMS Design System & Palette Constants.
Provides consistent colors, typography tokens, and shared stylesheet definitions.
"""

from pathlib import Path
import sys

NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"
SUCCESS_GREEN = "#15803D"
DANGER_RED = "#DC2626"
WARNING_AMBER = "#D97706"

GLOBAL_FONT_FAMILY = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

# Status Chip / Badge Palette
BADGE_GREEN_BG = "#DCFCE7"
BADGE_GREEN_FG = "#15803D"
BADGE_AMBER_BG = "#FEF3C7"
BADGE_AMBER_FG = "#B45309"
BADGE_RED_BG = "#FEE2E2"
BADGE_RED_FG = "#B91C1C"
BADGE_BLUE_BG = "#DBEAFE"
BADGE_BLUE_FG = "#1D4ED8"
BADGE_GRAY_BG = "#F3F4F6"
BADGE_GRAY_FG = "#4B5563"


def get_chevron_down_icon_path(color: str = NAVY) -> str:
    """
    Returns the absolute POSIX-style path to a clean SVG chevron-down icon.
    Auto-generates and caches the SVG file if not already present.
    """
    if hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS) / "app" / "resources" / "icons"
    else:
        base_dir = Path(__file__).resolve().parent.parent / "resources" / "icons"

    base_dir.mkdir(parents=True, exist_ok=True)
    slug = color.replace("#", "").lower()
    icon_path = base_dir / f"chevron-down-{slug}.svg"

    if not icon_path.exists():
        svg_code = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="6 9 12 15 18 9"></polyline></svg>'
        )
        icon_path.write_text(svg_code, encoding="utf-8")

    return icon_path.as_posix()


CHEVRON_DOWN_PATH = get_chevron_down_icon_path(NAVY)
CHEVRON_DOWN_DISABLED_PATH = get_chevron_down_icon_path(MUTED)


def get_app_icon_path() -> Path:
    """Returns path to the primary application icon (.png or .ico)."""
    if hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS) / "app" / "resources" / "icons"
    else:
        base_dir = Path(__file__).resolve().parent.parent / "resources" / "icons"

    if (base_dir / "app_icon.png").exists():
        return base_dir / "app_icon.png"
    if (base_dir / "app_icon.ico").exists():
        return base_dir / "app_icon.ico"
    return base_dir / "app_icon.svg"

