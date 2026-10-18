#!/usr/bin/env python3
"""Analyze, plan and edit running / race photos. Originals are never modified.

  python photo.py analyze <folder>            # metrics, previews, contact sheets, draft plan
  python photo.py apply <folder>/_revisao/plan.json [--only a.jpg,b.jpg]
  python photo.py zoom <photo> <x> <y>        # 100% crop at fractions x, y (focus check)
  python photo.py presets                     # print the presets and slider ranges

analyze writes everything to <folder>/_revisao/. apply writes the upload-ready
JPEGs to <folder>/editadas/ (or the plan's "output") and before/after sheets to
_revisao/. Needs Python 3.8+, numpy and Pillow. RAW files (.cr3, .cr2, .dng)
also need rawpy (pip install rawpy); when a RAW and a JPEG share a name, the RAW
is used.
"""

import argparse
import io
import json
import math
import os
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import numpy as np
from PIL import Image, ImageCms, ImageDraw, ImageFilter, ImageFont, ImageOps

JPEG_EXTS = {".jpg", ".jpeg"}
RAW_EXTS = {".cr3", ".cr2", ".dng"}
REVIEW_DIR = "_revisao"
OUTPUT_DIR = "editadas"
SRGB = ImageCms.createProfile("sRGB")
SRGB_ICC = ImageCms.ImageCmsProfile(SRGB).tobytes()

# Slider ranges. Most input is 8-bit JPEG, so the ranges are narrower than
# Lightroom's: beyond them a camera JPEG bands, posterizes or turns to noise.
RANGES = {
    "exposure": (-1.5, 1.5),   # stops
    "temp": (-100, 100),       # + warmer, - cooler (100 = half a stop on red and blue)
    "tint": (-100, 100),       # + magenta, - green
    "contrast": (-50, 50),
    "highlights": (-100, 100),
    "shadows": (-100, 100),
    "whites": (-50, 50),
    "blacks": (-50, 50),
    "clarity": (0, 50),
    "vibrance": (-50, 60),
    "saturation": (-100, 40),
    "blues": (-100, 30),       # saturation of blue/violet hues only (asphalt, sky), like Lightroom's HSL
    "warmth": (0, 60),         # golden color grade in the highlights and on sunlit skin
    "denoise": (0, 100),
    "sharpen": (0, 100),
    "vignette": (-50, 20),     # - darkens corners
    "bg_blur": (0, 30),        # fake shallow depth of field, kept subtle on purpose; needs rembg
}

# The look that sells is warm and lively: real contrast with deep blacks,
# vibrance (which spares skin) over saturation, a golden grade in the light.
# The first presets lifted shadows and pulled highlights with no contrast and
# read as cold and flat ("frias e secas") on real event photos.
PRESETS = {
    "nenhum": {},
    "neutro": {"contrast": 15, "blacks": -10, "clarity": 10, "vibrance": 20,
               "temp": 5, "warmth": 15, "sharpen": 30},
    "sol-forte": {"highlights": -30, "shadows": 20, "contrast": 25, "whites": 8, "blacks": -18,
                  "clarity": 15, "vibrance": 30, "temp": 8, "warmth": 30, "sharpen": 30},
    "sombra": {"temp": 15, "warmth": 25, "contrast": 20, "shadows": 15, "blacks": -12,
               "clarity": 15, "vibrance": 25, "sharpen": 30},
    "nublado": {"contrast": 30, "clarity": 20, "whites": 10, "blacks": -18,
                "vibrance": 30, "temp": 8, "warmth": 20, "sharpen": 35},
    "contraluz": {"shadows": 45, "highlights": -40, "contrast": 10, "blacks": -10,
                  "clarity": 10, "vibrance": 20, "temp": 6, "warmth": 20, "sharpen": 30},
    "golden": {"highlights": -25, "shadows": 15, "contrast": 15, "blacks": -10,
               "vibrance": 15, "warmth": 30, "sharpen": 30},
    "baixa-luz": {"denoise": 50, "shadows": 10, "blacks": -10, "contrast": 15,
                  "vibrance": 15, "warmth": 10, "sharpen": 15},
    "pb-impacto": {"saturation": -100, "contrast": 25, "clarity": 20,
                   "blacks": -10, "sharpen": 35},
}


class PlanError(Exception):
    pass


# ---------------------------------------------------------------- image io

def is_raw(name):
    return os.path.splitext(name)[1].lower() in RAW_EXTS


def list_photos(folder):
    """Photo files in folder; a JPEG is skipped when a RAW of the same name exists."""
    names = [n for n in os.listdir(folder)
             if os.path.splitext(n)[1].lower() in JPEG_EXTS | RAW_EXTS and os.path.isfile(os.path.join(folder, n))]
    raw_stems = {os.path.splitext(n)[0].lower() for n in names if is_raw(n)}
    return sorted(n for n in names if is_raw(n) or os.path.splitext(n)[0].lower() not in raw_stems)


def raw_exif(path):
    """EXIF of a RAW file. CR3 keeps it in CMT1 (IFD0) and CMT2 (Exif IFD) boxes;
    TIFF-based RAWs (CR2, DNG) are read by Pillow."""
    if not path.lower().endswith(".cr3"):
        try:
            return Image.open(path).getexif()
        except OSError:
            return Image.Exif()
    exif = Image.Exif()
    with open(path, "rb") as fh:
        head = fh.read(1 << 20)
    for box in (b"CMT1", b"CMT2"):
        at = head.find(box)
        if at < 4:
            continue
        size = int.from_bytes(head[at - 4:at], "big")
        part = Image.Exif()
        part.load(b"Exif\x00\x00" + head[at + 4:at - 4 + size])
        if box == b"CMT1":
            exif.update(part)
        else:
            exif[0x8769] = dict(part)
    return exif


def load(path, raw_exposure=0.0):
    """Open a photo upright in sRGB. Returns (image, exif, color_space).
    A RAW is developed here, with raw_exposure (stops) applied to the sensor data,
    where it still has the highlight headroom a JPEG has lost."""
    if not is_raw(path):
        return open_jpeg(path)
    try:
        import rawpy
    except ImportError:
        raise PlanError(f"{os.path.basename(path)} is RAW: install rawpy (pip install rawpy) or use the JPEG")
    with rawpy.imread(path) as raw:
        rgb = raw.postprocess(use_camera_wb=True, output_bps=16, highlight_mode=rawpy.HighlightMode.Blend,
                              exp_shift=2 ** max(-2, min(3, raw_exposure)), exp_preserve_highlights=0.8)
    return Image.fromarray(to_uint8(rgb.astype(np.float32) / 65535)), raw_exif(path), "sRGB"


def open_jpeg(path):
    """Open a JPEG upright and in sRGB. Returns (image, exif, color_space)."""
    im = Image.open(path)
    exif = im.getexif()
    icc = im.info.get("icc_profile")
    im = ImageOps.exif_transpose(im).convert("RGB")
    space = "sRGB"
    if icc:
        profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        space = ImageCms.getProfileDescription(profile).strip() or "unknown"
        if "srgb" not in space.lower():
            im = ImageCms.profileToProfile(im, profile, SRGB, outputMode="RGB")
    return im, exif, space


def read_exif(exif):
    sub = exif.get(0x8769) if isinstance(exif.get(0x8769), dict) else exif.get_ifd(0x8769)

    def num(v):
        return float(v) if v is not None else None

    shutter = num(sub.get(0x829A))
    stamp = sub.get(0x9003) or exif.get(0x0132)
    when = None
    if stamp:
        try:
            when = datetime.strptime(str(stamp).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
            subsec = str(sub.get(0x9291) or "0").strip("\x00 ") or "0"
            when = when.timestamp() + float("0." + subsec)
        except ValueError:
            when = None
    return {
        "camera": str(exif.get(0x0110) or "").strip("\x00 "),
        "shutter": shutter,
        "shutter_text": f"1/{round(1 / shutter)}" if shutter and shutter < 1 else (f"{shutter}s" if shutter else None),
        "aperture": num(sub.get(0x829D)),
        "iso": int(sub.get(0x8827)) if sub.get(0x8827) else None,
        "focal_mm": num(sub.get(0x920A)),
        "exposure_comp": num(sub.get(0x9204)),
        "timestamp": when,
    }


def save_jpeg(im, path, exif=None, quality=90):
    kwargs = {"quality": quality, "optimize": True, "icc_profile": SRGB_ICC}
    if exif is not None:
        exif[0x0112] = 1  # pixels are already upright
        kwargs["exif"] = exif.tobytes()
    im.save(path, "JPEG", **kwargs)


# ---------------------------------------------------------------- pixel math

def to_linear(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def to_gamma(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def luma(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


# ---------------------------------------------------------------- editing

def merged_params(preset, adjust):
    if preset not in PRESETS:
        raise PlanError(f"unknown preset '{preset}', use one of: {', '.join(PRESETS)}")
    unknown = set(adjust) - set(RANGES)
    if unknown:
        raise PlanError(f"unknown adjust keys {sorted(unknown)}, valid: {', '.join(RANGES)}")
    params = {k: PRESETS[preset].get(k, 0) + adjust.get(k, 0) for k in RANGES}
    return {k: min(max(v, RANGES[k][0]), RANGES[k][1]) for k, v in params.items()}


def geometry(im, rotate=0.0, crop=None):
    """Straighten (degrees, + is counter-clockwise), then crop (fractions [left, top, right, bottom])."""
    if rotate:
        w, h = im.size
        im = im.rotate(rotate, Image.BICUBIC)
        a = math.radians(abs(rotate))
        # largest same-aspect rectangle inside the rotated frame
        s = 1 / (math.cos(a) + max(w / h, h / w) * math.sin(a))
        x0, y0 = int(w * (1 - s) / 2), int(h * (1 - s) / 2)
        im = im.crop((x0, y0, w - x0, h - y0))
    if crop:
        left, top, right, bottom = crop
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise PlanError(f"crop {crop} must be fractions [left, top, right, bottom] with left<right, top<bottom")
        w, h = im.size
        im = im.crop((round(left * w), round(top * h), round(right * w), round(bottom * h)))
    return im


def tone_color(rgb, p):
    """Per-pixel edits: white balance, exposure, tone curve, vibrance, saturation.
    rgb: float32 (..., 3) sRGB in 0..1."""
    # white balance and exposure in linear light, with a soft highlight shoulder
    if p["temp"] or p["tint"] or p["exposure"]:
        # near-white pixels (blown sky, white shirts) stay as they were instead of
        # turning beige, green or flat gray: there is no detail left to correct
        white = np.clip((rgb.min(axis=-1) - 0.85) / 0.12, 0, 1)[..., None]
        before = rgb
        lin = to_linear(rgb)
        gains = np.array([2 ** (p["temp"] / 200), 2 ** (-p["tint"] / 200), 2 ** (-p["temp"] / 200)], np.float32)
        lin = lin * gains * 2 ** p["exposure"]
        knee = 0.8
        over = lin > knee
        lin[over] = knee + (1 - knee) * np.tanh((lin[over] - knee) / (1 - knee))
        rgb = to_gamma(lin).astype(np.float32)
        rgb = rgb * (1 - white) + before * white

    # tone curve on luminance: highlights, shadows, whites, blacks, contrast
    y = luma(rgb)
    f = y.copy()
    f += p["shadows"] / 100 * 1.6 * y * (1 - y) ** 2
    f += p["highlights"] / 100 * 1.6 * y ** 2 * (1 - y)
    f += p["whites"] / 100 * 0.15 * y ** 4
    f += p["blacks"] / 100 * 0.15 * (1 - y) ** 4
    f = np.clip(f, 0, 1)
    if p["contrast"]:
        s = f * f * (3 - 2 * f)
        f = np.clip(f + p["contrast"] / 100 * 1.5 * (s - f), 0, 1)
    ratio = np.clip(f / np.maximum(y, 1e-4), 0, 4)[..., None]
    # half multiplicative (keeps color), half additive (keeps lifted shadows from oversaturating)
    rgb = np.clip(0.5 * rgb * ratio + 0.5 * (rgb + (f - y)[..., None]), 0, 1)

    if p["vibrance"] or p["saturation"]:
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        hi, lo = rgb.max(axis=-1), rgb.min(axis=-1)
        # skin: orange hues (r >= g >= b, hue under ~40 degrees) at moderate saturation
        skin = (r >= g) & (g >= b) & (g - b < 0.67 * (r - b)) & (hi - lo > 0.15 * hi) & (hi - lo < 0.65 * hi)
        vib = p["vibrance"] / 100 * (1 - (hi - lo)) * np.where(skin, 0.4, 1.0)
        y = luma(rgb)[..., None]
        rgb = y + (rgb - y) * (1 + p["saturation"] / 100 + vib)[..., None]

    if p["blues"]:
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        hue = np.degrees(np.arctan2(math.sqrt(3) * (g - b), 2 * r - g - b)) % 360
        # full weight at 235 degrees (sky-lit asphalt), fading out by 185 and 285,
        # and only below sky brightness: the road loses its cast, the sky stays blue;
        # skin, foliage and magenta shirts are not touched
        # strongly saturated blues are clothing (a royal blue shirt), not road: spared
        sat = rgb.max(axis=-1) - rgb.min(axis=-1)
        weight = (np.clip(1 - np.abs(hue - 235) / 50, 0, 1) * np.clip((0.75 - luma(rgb)) / 0.2, 0, 1)
                  * np.clip((0.55 - sat) / 0.2, 0, 1))
        y = luma(rgb)[..., None]
        rgb = y + (rgb - y) * (1 + p["blues"] / 100 * weight)[..., None]

    if p["warmth"]:
        # color grade: a golden tint in the light (sunlit skin, highlights) while
        # shadows stay neutral; warmer and less fake than raising temp overall
        light = (np.clip(luma(rgb), 0, 1) ** 1.5)[..., None]
        rgb = rgb + p["warmth"] / 100 * light * np.array([0.07, 0.03, -0.05], np.float32)
    return np.clip(rgb, 0, 1)


def color_lut(p, size=65):
    """Bake tone_color into a 3D LUT, applied in C by Pillow (a .cube preset, in effect)."""
    axis = np.linspace(0, 1, size, dtype=np.float32)
    b, g, r = np.meshgrid(axis, axis, axis, indexing="ij")  # red varies fastest
    return ImageFilter.Color3DLUT(size, tone_color(np.stack([r, g, b], axis=-1), p).reshape(-1, 3))


def vignette(im, amount):
    w, h = im.size
    sw, sh = 256, max(1, round(256 * h / w))
    yy, xx = np.ogrid[0:sh, 0:sw]
    r2 = ((xx / sw - 0.5) ** 2 + (yy / sh - 0.5) ** 2) * 2
    mask = np.clip(r2 - 0.15, 0, 1) / 0.85 * abs(amount) / 100 * 0.5 * 255
    mask = Image.fromarray(mask.astype(np.uint8)).resize(im.size, Image.BILINEAR)
    return Image.composite(Image.new("RGB", im.size, "black" if amount < 0 else "white"), im, mask)


def denoise(im, amount):
    k = amount / 100
    y, cb, cr = im.convert("YCbCr").split()
    cb, cr = (Image.blend(c, c.filter(ImageFilter.GaussianBlur(1 + 3 * k)), k) for c in (cb, cr))
    # smooth luminance only where it is flat, so edges and the bib number stay crisp
    flat = y.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(2))
    flat = flat.point(lambda v: int(max(0, 255 - v * 12) * 0.7 * k))
    y = Image.composite(y.filter(ImageFilter.GaussianBlur(1.2)), y, flat)
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")


_SEGMENTER = []


def box_mean(a, r):
    """Mean over a (2r+1)^2 window, via an integral image."""
    s = np.pad(a, r + 1, mode="edge").cumsum(0).cumsum(1)
    k = 2 * r + 1
    return (s[k:, k:] - s[:-k, k:] - s[k:, :-k] + s[:-k, :-k])[:a.shape[0], :a.shape[1]] / (k * k)


def guided_filter(guide, src, r, eps):
    """He et al. guided filter: smooths src while following the edges of guide."""
    mean_i, mean_p = box_mean(guide, r), box_mean(src, r)
    a = (box_mean(guide * src, r) - mean_i * mean_p) / (box_mean(guide * guide, r) - mean_i ** 2 + eps)
    b = mean_p - a * mean_i
    return box_mean(a, r) * guide + box_mean(b, r)


def blur_background(im, amount):
    """Blur what is not a person, more the farther it sits above the runners' feet,
    so the road they stand on stays sharp like a real lens would keep it.
    Every person the model finds stays sharp: runners behind are customers too."""
    try:
        from rembg import new_session, remove
    except ImportError:
        raise PlanError("bg_blur needs rembg: pip install rembg onnxruntime (downloads a 170 MB model once)")
    if not _SEGMENTER:
        _SEGMENTER.append(new_session("u2net_human_seg"))
    small = im.copy()
    small.thumbnail((1280, 1280), Image.LANCZOS)
    mask = remove(small, session=_SEGMENTER[0], only_mask=True)
    coarse = np.asarray(mask, np.float32) / 255
    # the model sees 320 px and outlines people too wide, leaving a ring of sharp
    # background: shrink the outline, then snap it to the photo's real edges
    inner = np.asarray(mask.filter(ImageFilter.MinFilter(7)), np.float32) / 255
    pm = guided_filter(np.asarray(small.convert("L"), np.float32) / 255, inner, 4, 1e-4)
    # textured backgrounds (foliage) leave specks of sharp background: harden,
    # open (erode then dilate) to drop them, then soften the edge by a pixel
    hard = Image.fromarray((np.clip((pm - 0.35) / 0.3, 0, 1) * 255).astype(np.uint8))
    hard = hard.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1))
    pm = np.asarray(hard, np.float32) / 255
    rows = np.nonzero(pm.max(axis=1) > 0.5)[0]
    if not rows.size:
        return im
    h = pm.shape[0]
    ramp = np.clip((rows.max() - np.arange(h)) / (0.2 * h), 0, 1)[:, None]
    weight = Image.fromarray(((1 - pm) * ramp * 255).astype(np.uint8))

    # normalized convolution: blur the background with the runners cut out,
    # so their colors do not glow into the blurred area around them
    radius = amount / 100 * max(small.size) * 0.012
    keep = (coarse < 0.1).astype(np.float32)
    pixels = np.asarray(small, np.float32) * keep[..., None]
    num = np.stack([np.asarray(Image.fromarray(pixels[..., c].astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)), np.float32)
                    for c in range(3)], axis=2)
    den = np.asarray(Image.fromarray((keep * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)), np.float32)
    blurred = Image.fromarray(np.clip(num * 255 / np.maximum(den, 8)[..., None], 0, 255).astype(np.uint8))
    return Image.composite(blurred.resize(im.size, Image.BICUBIC), im, weight.resize(im.size, Image.BILINEAR))


def develop(im, p):
    """Apply merged slider values to an 8-bit RGB image, in Lightroom's order."""
    if any(p[k] for k in ("exposure", "temp", "tint", "contrast", "highlights", "shadows",
                          "whites", "blacks", "vibrance", "saturation", "blues", "warmth")):
        im = im.filter(color_lut(p))
    if p["denoise"]:
        im = denoise(im, p["denoise"])
    if p["clarity"]:  # local contrast: a wide, gentle unsharp mask (~1% of the frame)
        im = im.filter(ImageFilter.UnsharpMask(radius=max(im.size) / 100, percent=round(p["clarity"] * 1.2), threshold=0))
    if p["vignette"]:
        im = vignette(im, p["vignette"])
    if p["bg_blur"]:
        im = blur_background(im, p["bg_blur"])
    if p["sharpen"]:
        radius = max(0.6, max(im.size) / 6000)
        im = im.filter(ImageFilter.UnsharpMask(radius=radius, percent=round(p["sharpen"] * 2), threshold=3))
    return im


def to_uint8(rgb):
    noise = np.random.default_rng(0).random(rgb.shape[:2], np.float32)[..., None]  # dither against banding
    return np.clip(rgb * 255 + noise, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- analyze

def measure(im):
    rgb = np.asarray(im, np.float32) / 255
    y = luma(rgb)
    h, w = y.shape
    q = np.percentile(y, [2, 5, 50, 95, 98])
    hi = rgb.max(axis=2)
    sat = hi - rgb.min(axis=2)

    # sharpness of the crispest tile: low means nothing in the frame is sharp
    # (shake, missed focus). A sharp background with a blurred runner still
    # scores high, so the subject is checked by eye with `zoom`.
    lap = 4 * y[1:-1, 1:-1] - y[:-2, 1:-1] - y[2:, 1:-1] - y[1:-1, :-2] - y[1:-1, 2:]
    th, tw = lap.shape[0] // 4, lap.shape[1] // 4
    sharpness = max(lap[r * th:(r + 1) * th, c * tw:(c + 1) * tw].var() for r in range(4) for c in range(4))

    middle = y[h // 4:3 * h // 4, w // 4:3 * w // 4]
    # pure white in the middle of the frame: a blown face or white shirt, not sky
    center_blown = (rgb[h // 4:3 * h // 4, w // 4:3 * w // 4].min(axis=2) >= 0.98).mean()
    center = middle.mean()
    border = (y.sum() - middle.sum()) / (y.size - middle.size)

    # white balance from the ground: in a street race the lower third is mostly
    # asphalt, the most reliable gray card in the frame. Grass or dirt is not
    # neutral, so no reading is taken when the ground is colorful.
    ground = rgb[2 * h // 3:]
    gl = luma(ground)
    # strongly tinted asphalt can be quite saturated; green pixels are grass, not road
    green = (ground[..., 1] > ground[..., 0]) & (ground[..., 1] > ground[..., 2])
    gray = (gl > 0.04) & (gl < 0.8) & (ground.max(axis=2) - ground.min(axis=2) < 0.4) & ~green
    temp = tint = None
    if gray.mean() > 0.25:
        r, g, b = np.median(to_linear(ground[gray]), axis=0)
        a, c = math.log2(r / g), math.log2(b / g)
        temp, tint = -100 * (a - c), -100 * (a + c)

    return {
        "median": round(float(q[2]), 3), "p2": round(float(q[0]), 3), "p98": round(float(q[4]), 3),
        "contrast": round(float(q[3] - q[1]), 3),
        "clipped_highlights": round(float((hi >= 0.99).mean()), 4),
        "center_blown": round(float(center_blown), 4),
        "crushed_shadows": round(float((y <= 0.01).mean()), 4),
        "saturation": round(float(sat.mean()), 3),
        "center_vs_border": round(float(center / max(border, 1e-3)), 2),
        "border_brightness": round(float(border), 3),
        "sharpness": round(float(sharpness) * 1e4, 2),
        "wb_temp_fix": None if temp is None else round(temp),
        "wb_tint_fix": None if tint is None else round(tint),
    }


def suggest(m, ex):
    iso = ex["iso"] or 0
    if iso >= 3200 or (iso >= 1600 and m["median"] < 0.25):
        scene = "baixa-luz"
    elif m["center_vs_border"] < 0.75 and m["border_brightness"] > 0.5:
        scene = "contraluz"
    elif m["clipped_highlights"] > 0.01 and m["contrast"] > 0.7:
        scene = "sol-forte"
    elif m["contrast"] < 0.55:
        scene = "nublado"
    elif (m["wb_temp_fix"] or 0) > 12:
        scene = "sombra"
    else:
        scene = "neutro"

    def stops(target, value):
        return math.log2(float(to_linear(np.float32(target))) / max(float(to_linear(np.float32(value))), 1e-4))

    # Judge exposure by the histogram's ends, not the median: dark asphalt or a
    # white sky moves the median while the runner is exposed fine.
    adjust, ev = {}, 0.0
    if m["p98"] < 0.85:  # nothing near white: the whole frame is dull or dark
        ev = min(stops(0.92, m["p98"]), max(stops(0.45, m["median"]), 0))
    elif m["median"] > 0.62 and m["p2"] > 0.12:  # washed out, no real blacks
        ev = max(stops(0.5, m["median"]), -0.7)
    ev = round(max(-1.0, min(1.0, ev)) * 20) / 20
    if abs(ev) >= 0.15:
        adjust["exposure"] = ev
    # Sky-lit asphalt reads far bluer than the rest of the scene, so fully
    # neutralizing it with white balance turns skin and trees yellow. On real
    # event photos a gentle warm/green shift plus desaturating only the blue
    # hues (`blues`) gave a gray road with natural skin. Warm light flatters
    # skin and buyers like it, so cooling is nudged even less.
    for key, fix in (("temp", m["wb_temp_fix"]), ("tint", m["wb_tint_fix"])):
        if fix is None:
            continue
        value = round(max(-50, min(50, fix * (0.1 if key == "temp" and fix < 0 else 0.18 if key == "temp" else 0.15))))
        if abs(value) >= 5:
            adjust[key] = value
    if (m["wb_temp_fix"] or 0) > 40:  # `blues` spares the sky, so it can work hard on the road
        adjust["blues"] = -round(min(85, (m["wb_temp_fix"] - 40) * 0.6))
    if scene == "sombra" and "temp" in adjust:  # the preset already warms
        adjust["temp"] -= PRESETS["sombra"]["temp"]
        if abs(adjust["temp"]) < 5:
            del adjust["temp"]
    if iso >= 1600 and scene != "baixa-luz":
        adjust["denoise"] = 20 if iso < 3200 else 40
    return scene, adjust


def flags_for(m, ex, batch_sharpness):
    flags = []
    if batch_sharpness and m["sharpness"] < 0.4 * batch_sharpness:
        flags.append("soft")
    if ex["shutter"] and ex["shutter"] > 1 / 500:
        flags.append("slow-shutter")
    if (ex["iso"] or 0) >= 3200:
        flags.append("high-iso")
    if m["center_blown"] > 0.03:
        flags.append("blown-subject")
    if m["crushed_shadows"] > 0.05:
        flags.append("crushed-shadows")
    if m["median"] < 0.25 and m["p98"] < 0.8:
        flags.append("underexposed")
    if m["median"] > 0.62 and (m["p2"] > 0.12 or m["clipped_highlights"] > 0.02):
        flags.append("overexposed")
    if abs(m["wb_temp_fix"] or 0) > 60 or abs(m["wb_tint_fix"] or 0) > 60:
        flags.append("color-cast")
    return flags


def label_font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def contact_sheets(entries, review, previews, cols=4, rows=4, cell=400):
    font = label_font(15)
    pages = [entries[i:i + cols * rows] for i in range(0, len(entries), cols * rows)]
    names = []
    for n, page in enumerate(pages, 1):
        sheet = Image.new("RGB", (cols * cell, rows * (cell * 2 // 3 + 40)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, e in enumerate(page):
            x, y0 = (i % cols) * cell, (i // cols) * (cell * 2 // 3 + 40)
            thumb = Image.open(os.path.join(previews, e["preview"]))
            thumb.thumbnail((cell - 8, cell * 2 // 3 - 4))
            sheet.paste(thumb, (x + (cell - thumb.width) // 2, y0 + 4))
            text = f"#{e['index']} {os.path.splitext(e['file'])[0]}"
            draw.text((x + 6, y0 + cell * 2 // 3 + 2), text, fill="black", font=font)
            draw.text((x + 6, y0 + cell * 2 // 3 + 20), ",".join(e["flags"]) or "ok", fill="#b00" if e["flags"] else "#070", font=font)
        name = f"contato-{n:02d}.jpg"
        sheet.save(os.path.join(review, name), quality=85)
        names.append(name)
    return names


def zoom(path, x, y, size=800):
    """Save a 100% crop centred at fractions (x, y) of the upright photo, to check focus on a face or bib."""
    im = load(path)[0]
    cx, cy = x * im.width, y * im.height
    half = size // 2
    left = int(min(max(cx - half, 0), max(im.width - size, 0)))
    top = int(min(max(cy - half, 0), max(im.height - size, 0)))
    folder = os.path.join(os.path.dirname(os.path.abspath(path)), REVIEW_DIR, "zoom")
    os.makedirs(folder, exist_ok=True)
    out = os.path.join(folder, f"{os.path.splitext(os.path.basename(path))[0]}_{x:.2f}_{y:.2f}.jpg")
    im.crop((left, top, left + size, top + size)).save(out, quality=90)
    print(out)


def analyze_one(job):
    """Measure one photo and write its preview."""
    index, folder, name, review = job
    full, exif, space = load(os.path.join(folder, name))
    small = full.copy()
    small.thumbnail((1600, 1600), Image.LANCZOS)
    m = measure(small)
    stem = os.path.splitext(name)[0]
    small.thumbnail((1280, 1280), Image.LANCZOS)
    small.save(os.path.join(review, "previews", stem + ".jpg"), quality=85)
    return {"index": index, "file": name, "preview": stem + ".jpg",
            "width": full.width, "height": full.height, "color_space": space,
            "exif": read_exif(exif), "metrics": m}


def analyze(folder, jobs):
    folder = os.path.abspath(folder)
    names = list_photos(folder)
    if not names:
        sys.exit(f"no photos in {folder}")
    review = os.path.join(folder, REVIEW_DIR)
    previews = os.path.join(review, "previews")
    os.makedirs(previews, exist_ok=True)

    entries = []
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for entry in pool.map(analyze_one, [(i, folder, n, review) for i, n in enumerate(names, 1)]):
            entries.append(entry)
            print(f"[{entry['index']}/{len(names)}] {entry['file']}", file=sys.stderr)

    batch_sharpness = float(np.median([e["metrics"]["sharpness"] for e in entries]))
    for e in entries:
        e["flags"] = flags_for(e["metrics"], e["exif"], batch_sharpness)
        if "srgb" not in e["color_space"].lower():
            e["flags"].append("not-srgb")
        e["scene"], e["adjust"] = suggest(e["metrics"], e["exif"])

    # bursts: consecutive frames less than 1 s apart
    timed = sorted((e for e in entries if e["exif"]["timestamp"]), key=lambda e: e["exif"]["timestamp"])
    burst, last = 0, None
    for e in timed:
        if last is None or e["exif"]["timestamp"] - last > 1.0:
            burst += 1
        e["burst"] = burst
        last = e["exif"]["timestamp"]
    sizes = {}
    for e in timed:
        sizes[e["burst"]] = sizes.get(e["burst"], 0) + 1
    for e in entries:
        if sizes.get(e.get("burst"), 0) < 2:
            e["burst"] = None

    sheets = contact_sheets(entries, review, previews)
    shutters = [e["exif"]["shutter"] for e in entries if e["exif"]["shutter"]]
    isos = [e["exif"]["iso"] for e in entries if e["exif"]["iso"]]
    summary = {
        "photos": len(entries),
        "bursts": len({e["burst"] for e in entries if e["burst"]}),
        "flag_counts": {f: sum(f in e["flags"] for e in entries) for f in sorted({f for e in entries for f in e["flags"]})},
        "scene_counts": {s: sum(e["scene"] == s for e in entries) for s in sorted({e["scene"] for e in entries})},
        "shutter_slowest": f"1/{round(1 / max(shutters))}" if shutters else None,
        "share_slower_than_1_500": round(sum(s > 1 / 500 for s in shutters) / len(shutters), 2) if shutters else None,
        "iso_range": [min(isos), max(isos)] if isos else None,
        "batch_median_sharpness": round(batch_sharpness, 2),
    }
    with open(os.path.join(review, "analysis.json"), "w", encoding="utf-8") as fh:
        json.dump({"source": folder, "summary": summary, "sheets": sheets, "images": entries}, fh, indent=1, ensure_ascii=False)

    # never overwrite a plan that may already hold review decisions
    plan_path = os.path.join(review, "plan.json")
    if os.path.exists(plan_path):
        plan_path = os.path.join(review, "plan-draft.json")
    plan = {"source": folder, "output": os.path.join(folder, OUTPUT_DIR), "quality": 90, "images": [
        {"file": e["file"], "action": "edit", "preset": e["scene"], "adjust": e["adjust"],
         "crop": None, "rotate": 0, "note": ""} for e in entries]}
    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1, ensure_ascii=False)
    print(json.dumps({"review": review, "plan": plan_path, "summary": summary, "sheets": sheets}, indent=1, ensure_ascii=False))


# ---------------------------------------------------------------- apply

def apply_one(job):
    src, dst, item, quality = job
    params = merged_params(item["preset"], item.get("adjust") or {})
    raw_exposure = params["exposure"] if is_raw(src) else 0.0
    im, exif, _ = load(src, raw_exposure)
    params["exposure"] -= raw_exposure
    im = develop(geometry(im, item.get("rotate") or 0, item.get("crop")), params)
    save_jpeg(im, dst, exif, quality)
    return item["file"]


def before_after(pairs, review, prefix="antes-depois", width=1400):
    font = label_font(18)
    half = width // 2
    names = []
    for n in range(0, len(pairs), 3):
        chunk = pairs[n:n + 3]
        row_h = half * 2 // 3 + 30
        sheet = Image.new("RGB", (width, row_h * len(chunk)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, (name, before, after) in enumerate(chunk):
            for j, path in enumerate((before, after)):
                im = Image.open(path)
                im.draft("RGB", (half, half))
                im = im.convert("RGB")
                im.thumbnail((half - 8, half * 2 // 3 - 4))
                sheet.paste(im, (j * half + (half - im.width) // 2, i * row_h + 28))
            draw.text((6, i * row_h + 4), f"{name}   antes | depois", fill="black", font=font)
        out = f"{prefix}-{n // 3 + 1:02d}.jpg"
        sheet.save(os.path.join(review, out), quality=85)
        names.append(out)
    return names


def apply(plan_path, jobs, only=None):
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    source = os.path.abspath(plan["source"])
    output = os.path.abspath(plan.get("output") or os.path.join(source, OUTPUT_DIR))
    if os.path.normcase(output) == os.path.normcase(source):
        raise PlanError("output must not be the source folder: originals are never overwritten")
    review = os.path.join(source, REVIEW_DIR)
    quality = int(plan.get("quality", 90))
    os.makedirs(output, exist_ok=True)

    actions = {"edit": [], "keep": [], "reject": []}
    for item in plan["images"]:
        if only and item["file"] not in only:
            continue
        if item.get("action") not in actions:
            raise PlanError(f"{item.get('file')}: action must be edit, keep or reject")
        if item["action"] == "edit":
            merged_params(item["preset"], item.get("adjust") or {})  # fail fast on a bad plan
        actions[item["action"]].append(item)

    def target(item):
        name = item["file"]
        return os.path.join(output, os.path.splitext(name)[0] + ".jpg" if is_raw(name) else name)

    for item in actions["reject"]:  # drop what an earlier run wrote, so it is never uploaded
        if os.path.exists(target(item)):
            os.remove(target(item))
    for item in actions["keep"]:
        if is_raw(item["file"]):  # a RAW cannot be uploaded as is: render it untouched
            actions["edit"].append({**item, "preset": "nenhum", "adjust": {}})
        else:
            shutil.copy2(os.path.join(source, item["file"]), target(item))
    work = [(os.path.join(source, it["file"]), target(it), it, quality) for it in actions["edit"]]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for i, name in enumerate(pool.map(apply_one, work), 1):
            print(f"[{i}/{len(work)}] {name}", file=sys.stderr)

    previews = os.path.join(review, "previews")
    pairs = []
    for it in actions["edit"]:
        before = os.path.join(previews, os.path.splitext(it["file"])[0] + ".jpg")
        pairs.append((it["file"], before if os.path.exists(before) else os.path.join(source, it["file"]), target(it)))
    # a partial re-run gets its own sheets instead of overwriting the full run's
    sheets = before_after(pairs, review, "retoque" if only else "antes-depois") if pairs else []
    print(json.dumps({"output": output, "edited": len(actions["edit"]), "kept": len(actions["keep"]),
                      "rejected": [it["file"] for it in actions["reject"]], "before_after": sheets},
                     indent=1, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    jobs = max(1, min(6, (os.cpu_count() or 2) // 2))
    an = sub.add_parser("analyze")
    an.add_argument("folder")
    an.add_argument("--jobs", type=int, default=jobs, help=f"parallel workers (default {jobs})")
    ap = sub.add_parser("apply")
    ap.add_argument("plan")
    ap.add_argument("--jobs", type=int, default=jobs, help=f"parallel workers (default {jobs}, ~0.5 GB each on 24 MP)")
    ap.add_argument("--only", help="comma-separated file names: re-apply just these (after tweaking the plan)")
    zp = sub.add_parser("zoom")
    zp.add_argument("photo")
    zp.add_argument("x", type=float, help="0 = left edge, 1 = right edge")
    zp.add_argument("y", type=float, help="0 = top, 1 = bottom")
    sub.add_parser("presets")
    args = parser.parse_args()
    try:
        if args.cmd == "analyze":
            analyze(args.folder, max(1, args.jobs))
        elif args.cmd == "apply":
            apply(args.plan, max(1, args.jobs), set(args.only.split(",")) if args.only else None)
        elif args.cmd == "zoom":
            zoom(args.photo, args.x, args.y)
        else:
            print(json.dumps({"ranges": RANGES, "presets": PRESETS}, indent=1))
    except PlanError as exc:
        sys.exit(f"plan error: {exc}")


if __name__ == "__main__":
    main()
