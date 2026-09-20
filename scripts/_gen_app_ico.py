"""Build resources/icons/app.ico with readable 16/32px frames from app.png."""

from __future__ import annotations

import io
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parents[1]
PNG = REPO / "resources" / "icons" / "app.png"
ICO = REPO / "resources" / "icons" / "app.ico"
PREVIEW = REPO / "build" / "icon-preview"

GOLD = (212, 160, 23, 255)
WHITE = (255, 255, 255, 255)
OUTLINE = (62, 42, 18, 255)

# Source layout (883x883): head left, trident right, eyes in the head.
HEAD_BOX = (90, 45, 545, 845)
FULL_PAD_BOX = None  # tight alpha bbox


def _masks(src: Image.Image) -> tuple[Image.Image, Image.Image]:
    arr = np.asarray(src)
    a = arr[:, :, 3]
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    gold = (a > 128) & (r > 140) & (g > 90) & (b < 130)
    white = (a > 200) & (r > 220) & (g > 220) & (b > 220)
    gold_i = Image.fromarray((gold.astype(np.uint8) * 255), mode="L")
    white_i = Image.fromarray((white.astype(np.uint8) * 255), mode="L")
    return gold_i, white_i


def _thicken(mask: Image.Image, px: int) -> Image.Image:
    if px <= 1:
        return mask
    odd = px if px % 2 else px + 1
    return mask.filter(ImageFilter.MaxFilter(odd))


def _fit_pair(
    gold: Image.Image,
    white: Image.Image,
    box: tuple[int, int, int, int],
    canvas: int,
    pad: int,
) -> tuple[Image.Image, Image.Image]:
    g = gold.crop(box)
    w = white.crop(box)
    union = np.maximum(np.asarray(g), np.asarray(w))
    ys, xs = np.where(union > 0)
    if len(xs) == 0:
        empty = Image.new("L", (canvas, canvas), 0)
        return empty, empty
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    g = g.crop(bbox)
    w = w.crop(bbox)
    inner = max(1, canvas - 2 * pad)
    cw, ch = g.size
    scale = min(inner / cw, inner / ch)
    nw, nh = max(1, round(cw * scale)), max(1, round(ch * scale))
    ox, oy = (canvas - nw) // 2, (canvas - nh) // 2
    g_out = Image.new("L", (canvas, canvas), 0)
    w_out = Image.new("L", (canvas, canvas), 0)
    g_out.paste(g.resize((nw, nh), Image.Resampling.LANCZOS), (ox, oy))
    w_out.paste(w.resize((nw, nh), Image.Resampling.LANCZOS), (ox, oy))
    return g_out, w_out


def _threshold(mask: Image.Image, cut: int = 90) -> Image.Image:
    return mask.point(lambda p: 255 if p >= cut else 0, mode="L")


def _outline(alpha: Image.Image, width: int) -> Image.Image:
    if width <= 0:
        return Image.new("L", alpha.size, 0)
    odd = width * 2 + 1
    grown = alpha.filter(ImageFilter.MaxFilter(odd))
    return Image.fromarray(
        np.clip(np.asarray(grown).astype(np.int16) - np.asarray(alpha).astype(np.int16), 0, 255).astype(
            np.uint8
        ),
        mode="L",
    )


def _compose(gold_a: Image.Image, white_a: Image.Image, outline_a: Image.Image) -> Image.Image:
    h, w = gold_a.size[1], gold_a.size[0]
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    ol = np.asarray(outline_a) > 0
    gd = np.asarray(gold_a) > 0
    wh = np.asarray(white_a) > 0
    rgba[ol] = OUTLINE
    rgba[gd] = GOLD
    rgba[wh] = WHITE
    return Image.fromarray(rgba, "RGBA")


def render_hires(src: Image.Image, size: int) -> Image.Image:
    """Tight-crop the original art for 64px and up (taskbar uses 16/32)."""
    alpha = src.split()[-1]
    box = alpha.getbbox()
    assert box is not None
    cropped = src.crop(box)
    pad = max(2, round(size * 0.06))
    inner = max(1, size - 2 * pad)
    w, h = cropped.size
    scale = min(inner / w, inner / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    fitted = cropped.resize((nw, nh), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(fitted, ((size - nw) // 2, (size - nh) // 2), fitted)
    return out


def render_size(
    gold: Image.Image,
    white: Image.Image,
    size: int,
    *,
    head: bool,
    gold_thick: dict[int, Image.Image],
) -> Image.Image:
    box = HEAD_BOX if head else gold.getbbox()
    assert box is not None
    work = min(256, max(64, size * 8))
    pad = max(4, work // 12)
    thicken = 15 if size <= 24 else 11 if size <= 48 else 5
    g = gold_thick[thicken]
    # Original eye holes (not thickened) so they stay round and aligned.
    wmask = white
    g = Image.fromarray(np.where(np.asarray(wmask) > 128, 0, np.asarray(g)).astype(np.uint8), mode="L")
    g_fit, w_fit = _fit_pair(g, wmask, box, work, pad)
    g_small = _threshold(g_fit.resize((size, size), Image.Resampling.LANCZOS), 100)
    if size <= 24:
        w_small = _stamp_eyes(g_small, size)
    else:
        w_small = _threshold(w_fit.resize((size, size), Image.Resampling.LANCZOS), 160)
        neighborhood = g_small.filter(ImageFilter.MaxFilter(3))
        w_small = Image.fromarray(
            np.where(np.asarray(neighborhood) > 0, np.asarray(w_small), 0).astype(np.uint8),
            mode="L",
        )
    ol = _outline(g_small, 1 if size <= 48 else 0)
    ol = Image.fromarray(
        np.where(np.asarray(w_small) > 0, 0, np.asarray(ol)).astype(np.uint8),
        mode="L",
    )
    return _compose(g_small, w_small, ol)


def _stamp_eyes(gold_a: Image.Image, size: int) -> Image.Image:
    """Two compact white pupils inside the gold silhouette (16/24px)."""
    g = np.asarray(gold_a) > 0
    ys, xs = np.where(g)
    out = np.zeros_like(np.asarray(gold_a))
    if len(xs) == 0:
        return Image.fromarray(out, mode="L")
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    cx_l = x0 + (x1 - x0) * 0.38
    cx_r = x0 + (x1 - x0) * 0.68
    cy = y0 + (y1 - y0) * 0.42
    radius = 1 if size <= 16 else 2
    yy, xx = np.ogrid[: size, : size]
    for cx in (cx_l, cx_r):
        disk = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
        out[disk & g] = 255
    return Image.fromarray(out, mode="L")


def write_ico(path: Path, frames: list[Image.Image]) -> None:
    blobs: list[bytes] = []
    for frame in frames:
        buf = io.BytesIO()
        frame.save(buf, format="PNG")
        blobs.append(buf.getvalue())
    count = len(frames)
    offset = 6 + 16 * count
    parts = [struct.pack("<HHH", 0, 1, count)]
    for frame, blob in zip(frames, blobs, strict=True):
        w, h = frame.size
        parts.append(
            struct.pack(
                "<BBBBHHII",
                0 if w >= 256 else w,
                0 if h >= 256 else h,
                0,
                0,
                0,
                32,
                len(blob),
                offset,
            )
        )
        offset += len(blob)
    path.write_bytes(b"".join(parts) + b"".join(blobs))


def main() -> None:
    src = Image.open(PNG).convert("RGBA")
    gold, white = _masks(src)
    gold_thick = {px: _thicken(gold, px) for px in (5, 11, 15)}
    PREVIEW.mkdir(parents=True, exist_ok=True)
    sizes = (16, 24, 32, 48, 64, 128, 256)
    frames: list[Image.Image] = []
    for size in sizes:
        if size >= 64:
            frame = render_hires(src, size)
        else:
            frame = render_size(
                gold,
                white,
                size,
                head=size <= 24,
                gold_thick=gold_thick,
            )
        frames.append(frame)
        scaled = frame.resize((size * 8, size * 8), Image.Resampling.NEAREST)
        scaled.save(PREVIEW / f"preview_{size}.png")
        frame.save(PREVIEW / f"native_{size}.png")
        opaque = int((np.asarray(frame)[:, :, 3] > 0).sum())
        print(f"{size}x{size} opaque={opaque}")
    write_ico(ICO, frames)
    print("wrote", ICO, ICO.stat().st_size)


if __name__ == "__main__":
    main()
