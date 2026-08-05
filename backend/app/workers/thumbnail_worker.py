"""
Thumbnail Worker (Ch.15: "Thumbnail generation... Worker... 5-15 seconds").

Note the naming overlap this module deliberately does NOT resolve the
same way: `ai/agents/thumbnail_agent.py` (Ch.07, Phase 4) produces a
thumbnail *brief* — headline text, visual concept, style, as JSON, no
pixels — explicitly scoped that way in that file's own docstring
("no image is rendered yet. That's the render pipeline, out of scope
until later phases."). This module is that later phase: it takes the
brief LangGraph already produced and rasterizes it into an actual PNG.
Two different files, two different jobs, same word in both names on
purpose — one plans the thumbnail, this one draws it.

Rendering approach: a flat brand-colored background (from the channel's
`brand.logo_position`-adjacent styling, kept simple — this is not a
design tool) with the brief's `headline_text` laid out in large bold
type, auto-shrunk to fit the canvas width. The auto-shrink logic mirrors
the old pipeline's caption-overflow fix (per this project's history:
"Caption overflow fixed with auto-shrink font logic") rather than
reinventing that from scratch.

No external API call here (unlike voice_worker/upload_worker) — Pillow
does everything locally, so there's nothing to retry against a flaky
network. `autoretry_for` is kept anyway for the one real failure mode
that does exist: a system font file missing on a given host.
"""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.workers.celery_app import celery_app
from app.workers.storage import persist, run_dir

CANVAS_SIZE = (1280, 720)  # YouTube's standard thumbnail resolution
MARGIN = 80
MAX_FONT_SIZE = 120
MIN_FONT_SIZE = 40

# A few style -> (background, text) color pairs. Extend as new
# thumbnail_style values show up from real channels (Ch.12d form).
_STYLE_COLORS: dict[str, tuple[str, str]] = {
    "bold_text_high_contrast": ("#0B0F19", "#FFFFFF"),
    "warm_editorial": ("#F4E9DA", "#2B1B0E"),
}
_DEFAULT_COLORS = _STYLE_COLORS["bold_text_high_contrast"]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    # DejaVuSans-Bold ships with Pillow's own test fonts on most Linux
    # distros/containers; falls back to Pillow's built-in bitmap font
    # (fixed size, ugly but never crashes) if truly unavailable, so a
    # missing system font degrades the thumbnail's looks, not the run.
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int) -> ImageFont.FreeTypeFont:
    size = MAX_FONT_SIZE
    while size > MIN_FONT_SIZE:
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font
        size -= 4
    return _load_font(MIN_FONT_SIZE)


@celery_app.task(
    name="workers.generate_thumbnail",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def generate_thumbnail(payload: dict[str, Any]) -> dict[str, Any]:
    channel_id = payload["channel_id"]
    run_id = payload["run_id"]
    brief = payload.get("thumbnail_brief") or {}
    headline = brief.get("headline_text", payload.get("channel_config", {}).get("name", "AI CarryON"))
    style = brief.get("style", "bold_text_high_contrast")

    bg_color, text_color = _STYLE_COLORS.get(style, _DEFAULT_COLORS)

    image = Image.new("RGB", CANVAS_SIZE, bg_color)
    draw = ImageDraw.Draw(image)

    max_text_width = CANVAS_SIZE[0] - 2 * MARGIN
    font = _fit_text(draw, headline, max_text_width)
    bbox = draw.textbbox((0, 0), headline, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (CANVAS_SIZE[0] - text_w) / 2
    y = (CANVAS_SIZE[1] - text_h) / 2
    draw.text((x, y), headline, font=font, fill=text_color)

    thumbnail_path = run_dir(channel_id, run_id) / "thumbnail.png"
    image.save(thumbnail_path, "PNG")
    storage_ref = persist(thumbnail_path, channel_id, run_id)

    return {**payload, "thumbnail_path": storage_ref}
