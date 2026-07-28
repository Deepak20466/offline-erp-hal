"""Central reference to the official HAL logo asset, used across every export format."""
from functools import lru_cache

from PIL import Image as PILImage

from app.config import BASE_DIR

LOGO_PATH = str(BASE_DIR / "app" / "static" / "images" / "hal-logo.jpeg")


@lru_cache(maxsize=1)
def _logo_aspect_ratio() -> float:
    """height/width ratio of the source logo file, so exports never stretch it."""
    with PILImage.open(LOGO_PATH) as img:
        width, height = img.size
    return height / width


def logo_dimensions_pt(target_width_pt: float) -> tuple[float, float]:
    """Return (width, height) in points for a given target width, preserving aspect ratio."""
    return target_width_pt, target_width_pt * _logo_aspect_ratio()
