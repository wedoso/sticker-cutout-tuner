#!/usr/bin/env python3
"""Local tuning UI for sticker cutout parameters."""

from __future__ import annotations

import base64
import io
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from PIL import Image, ImageChops, ImageDraw

from process_stickers import DEFAULT_PARAMS, params_from_dict, process_image, render_sticker


BASE_DIR = Path(__file__).resolve().parent


def configured_path(env_name: str, default: str) -> Path:
    value = os.environ.get(env_name)
    if not value:
        return BASE_DIR / default
    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


ORIGINAL_DIR = configured_path("STICKER_INPUT_DIR", "original")
OUTPUT_DIR = configured_path("STICKER_OUTPUT_DIR", "output")
PARAMS_PATH = configured_path("STICKER_PARAMS_PATH", "sticker_params.json")

app = Flask(__name__)


PARAM_GROUPS = [
    {
        "title": "Backing",
        "items": [
            ["outline_px", "Outline", 0, 36, 1],
            ["edge_smooth_px", "Edge smooth", 0.2, 8.0, 0.1],
            ["backing_feather_px", "Backing feather", 0.2, 5.0, 0.1],
            ["backing_min_area", "Backing min area", 0, 2000, 10],
            ["shape_close_px", "Shape close", 1, 8, 1],
        ],
    },
    {
        "title": "Shadow",
        "items": [
            ["shadow_blur_px", "Blur", 0, 18, 0.5],
            ["shadow_opacity", "Opacity", 0, 120, 1],
            ["shadow_offset_x", "Offset X", -20, 20, 1],
            ["shadow_offset_y", "Offset Y", -20, 24, 1],
        ],
    },
    {
        "title": "Content",
        "items": [
            ["content_feather_px", "Content feather", 0.2, 4.0, 0.1],
            ["min_body_area", "Body area", 20000, 260000, 5000],
            ["body_texture", "Body texture", 0, 1, 1],
            ["art_saturation_min", "Art saturation", 0, 40, 1],
            ["art_diff_min", "Art diff", 0, 30, 1],
            ["art_dark_value_max", "Art dark value", 160, 255, 1],
            ["art_dark_diff_min", "Art dark diff", 0, 40, 1],
            ["art_strong_diff", "Art strong diff", 30, 130, 1],
        ],
    },
    {
        "title": "Shape",
        "items": [
            ["shape_saturation_min", "Shape saturation", 0, 35, 1],
            ["shape_diff_min", "Shape diff", 0, 25, 1],
            ["shape_dark_value_max", "Shape dark value", 180, 255, 1],
            ["shape_dark_diff_min", "Shape dark diff", 0, 45, 1],
            ["shape_gradient_min", "Shape gradient", 0, 20, 0.5],
            ["shape_strong_diff", "Shape strong diff", 25, 120, 1],
            ["adjacent_radius_px", "Adjacent radius", 0, 8, 1],
        ],
    },
    {
        "title": "Neutral Texture",
        "items": [
            ["neutral_saturation_max", "Neutral sat max", 0, 40, 1],
            ["neutral_value_max", "Neutral value max", 210, 255, 1],
            ["neutral_diff_min", "Neutral diff", 0, 35, 1],
            ["neutral_gradient_min", "Neutral gradient", 0, 25, 0.5],
        ],
    },
    {
        "title": "Anchor",
        "items": [
            ["anchor_saturation_min", "Anchor saturation", 0, 45, 1],
            ["anchor_diff_min", "Anchor diff", 0, 35, 1],
            ["anchor_dark_value_max", "Anchor dark value", 150, 255, 1],
            ["anchor_dark_diff_min", "Anchor dark diff", 0, 45, 1],
            ["anchor_strong_diff", "Anchor strong diff", 30, 140, 1],
        ],
    },
    {
        "title": "Adjacent",
        "items": [
            ["adjacent_saturation_min", "Adjacent saturation", 0, 25, 1],
            ["adjacent_diff_min", "Adjacent diff", 0, 25, 1],
            ["adjacent_dark_value_max", "Adjacent dark value", 200, 255, 1],
            ["adjacent_dark_diff_min", "Adjacent dark diff", 0, 45, 1],
            ["adjacent_gradient_min", "Adjacent gradient", 0, 25, 0.5],
        ],
    },
]

QUICK_CONTROLS = [
    ["outline_px", "Outline", "New white border width. Lower this if the sticker looks too thick.", 0, 24, 1],
    ["cleanup_strength", "Old Edge Cleanup", "Higher removes more of the source white edge and old shadow. Use this for double boundaries.", 0, 100, 1],
    ["edge_smooth_px", "Edge Roundness", "Higher rounds and smooths the rebuilt border.", 0.5, 8.0, 0.1],
    ["shadow_opacity", "Shadow Strength", "Lower this if the image looks like it has two shadows.", 0, 90, 1],
    ["shadow_blur_px", "Shadow Softness", "Higher makes the one generated shadow softer.", 0, 18, 0.5],
    ["content_feather_px", "Art Edge Softness", "Softens the copied character/text edge.", 0.2, 3.0, 0.1],
]

PRESETS = [
    {
        "id": "doubleEdge",
        "label": "Fix Double Edge",
        "description": "For morning/hug-style bottom double borders.",
        "params": {
            "outline_px": 8,
            "edge_smooth_px": 4.8,
            "backing_feather_px": 1.8,
            "content_feather_px": 0.9,
            "shadow_blur_px": 5.5,
            "shadow_opacity": 26,
            "shadow_offset_x": 2,
            "shadow_offset_y": 3,
            "shape_close_px": 3,
            "backing_min_area": 220,
        },
        "cleanupStrength": 78,
    },
    {
        "id": "smoothEdge",
        "label": "Smoother Edge",
        "description": "Rounds jagged sticker edges.",
        "params": {
            "edge_smooth_px": 5.4,
            "backing_feather_px": 2.1,
            "shape_close_px": 3,
        },
    },
    {
        "id": "preserveDetail",
        "label": "Preserve Detail",
        "description": "Keeps more light clothing/text detail.",
        "params": {
            "outline_px": 10,
            "content_feather_px": 1.2,
            "body_texture": 1,
        },
        "cleanupStrength": 35,
    },
    {
        "id": "lightShadow",
        "label": "Light Shadow",
        "description": "Useful when shadow looks doubled.",
        "params": {
            "shadow_blur_px": 5.5,
            "shadow_opacity": 22,
            "shadow_offset_x": 2,
            "shadow_offset_y": 3,
        },
    },
]


def image_names() -> list[str]:
    return sorted(path.name for path in ORIGINAL_DIR.glob("*.png"))


def safe_image_path(name: str, directory: Path) -> Path:
    if name not in image_names():
        abort(404)
    path = directory / name
    if not path.exists():
        abort(404)
    return path


def load_saved_params() -> dict[str, dict]:
    if not PARAMS_PATH.exists():
        return {}
    return json.loads(PARAMS_PATH.read_text())


def write_saved_params(data: dict[str, dict]) -> None:
    PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PARAMS_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def data_url(image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def crop_to_alpha(image, padding: int = 24):
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return image, [0, 0, image.width, image.height]
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width, right + padding)
    bottom = min(image.height, bottom + padding)
    return image.crop((left, top, right, bottom)), [left, top, right, bottom]


def preview_image(path: Path, params: dict, max_size: int):
    sticker = render_sticker(path, params_from_dict(params))
    sticker, crop_box = crop_to_alpha(sticker)
    crop_size = [sticker.width, sticker.height]
    sticker.thumbnail((max_size, max_size))
    return sticker, crop_box, crop_size


def stroke_mask(size: tuple[int, int], mapped: list[tuple[float, float]], width: int) -> Image.Image:
    oversample = 3
    high_size = (size[0] * oversample, size[1] * oversample)
    high_mask = Image.new("L", high_size, 0)
    draw = ImageDraw.Draw(high_mask)
    high_points = [(x * oversample, y * oversample) for x, y in mapped]
    high_width = max(1, int(round(width * oversample)))
    radius = high_width / 2

    if len(high_points) > 1:
        draw.line(high_points, fill=255, width=high_width, joint="curve")
    for x, y in high_points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)

    return high_mask.resize(size, Image.Resampling.LANCZOS)


def connected_region_mask(
    image: Image.Image,
    seed: tuple[float, float],
    tolerance: int = 36,
    grow_px: int = 0,
    alpha_min: int = 8,
) -> Image.Image:
    rgba = np.array(image.convert("RGBA"))
    height, width = rgba.shape[:2]
    seed_x = int(round(seed[0]))
    seed_y = int(round(seed[1]))
    if seed_x < 0 or seed_x >= width or seed_y < 0 or seed_y >= height:
        return Image.new("L", (width, height), 0)
    if int(rgba[seed_y, seed_x, 3]) < alpha_min:
        return Image.new("L", (width, height), 0)

    rgb = rgba[:, :, :3].copy()
    mask = np.zeros((height + 2, width + 2), dtype=np.uint8)
    tol = max(0, int(round(tolerance)))
    flags = 8 | cv2.FLOODFILL_FIXED_RANGE | cv2.FLOODFILL_MASK_ONLY | (255 << 8)
    cv2.floodFill(rgb, mask, (seed_x, seed_y), (0, 0, 0), (tol, tol, tol), (tol, tol, tol), flags)
    selected = mask[1:-1, 1:-1]
    selected = np.where((selected > 0) & (rgba[:, :, 3] >= alpha_min), 255, 0).astype(np.uint8)
    grow = max(0, int(round(grow_px)))
    if grow:
        kernel_size = grow * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        selected = cv2.dilate(selected, kernel, iterations=1)
    return Image.fromarray(selected, "L")


def apply_manual_strokes(image, strokes: list[dict], crop_box: list[int], preview_size: list[int]):
    if not strokes:
        return image

    image = image.convert("RGBA")
    left, top, right, bottom = [float(value) for value in crop_box]
    preview_width, preview_height = [max(1.0, float(value)) for value in preview_size]
    scale_x = (right - left) / preview_width
    scale_y = (bottom - top) / preview_height
    scale = (scale_x + scale_y) / 2

    for stroke in strokes:
        tool = stroke.get("tool", "white")
        if tool in {"area-delete", "areaDelete"}:
            seed = stroke.get("seed") or {}
            try:
                mapped_seed = (
                    left + float(seed["x"]) * scale_x,
                    top + float(seed["y"]) * scale_y,
                )
                tolerance = int(round(float(stroke.get("tolerance", 36))))
                grow = int(round(float(stroke.get("grow", 3)) * scale))
            except (KeyError, TypeError, ValueError):
                continue
            mask = connected_region_mask(image, mapped_seed, tolerance=tolerance, grow_px=grow)
            image.putalpha(ImageChops.subtract(image.getchannel("A"), mask))
            continue

        points = stroke.get("points") or []
        if not points:
            continue
        width = max(1, int(round(float(stroke.get("size", 18)) * scale)))
        try:
            mapped = [
                (
                    left + float(point["x"]) * scale_x,
                    top + float(point["y"]) * scale_y,
                )
                for point in points
            ]
        except (KeyError, TypeError, ValueError):
            continue

        mask = stroke_mask(image.size, mapped, width)
        if tool in {"erase", "eraser"}:
            image.putalpha(ImageChops.subtract(image.getchannel("A"), mask))
        else:
            white_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
            white_layer.putalpha(mask)
            image = Image.alpha_composite(image, white_layer)
    return image


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def state():
    saved = load_saved_params()
    return jsonify(
        {
            "images": image_names(),
            "defaults": asdict(DEFAULT_PARAMS),
            "groups": PARAM_GROUPS,
            "quickControls": QUICK_CONTROLS,
            "presets": PRESETS,
            "saved": saved,
        }
    )


@app.get("/original/<path:name>")
def original(name: str):
    safe_image_path(name, ORIGINAL_DIR)
    return send_from_directory(ORIGINAL_DIR, name)


@app.get("/output/<path:name>")
def output(name: str):
    safe_image_path(name, OUTPUT_DIR)
    return send_from_directory(OUTPUT_DIR, name)


@app.post("/api/preview")
def preview():
    payload = request.get_json(force=True)
    name = payload.get("image")
    params = payload.get("params", {})
    max_size = int(payload.get("maxSize", 980))

    path = safe_image_path(name, ORIGINAL_DIR)
    start = time.perf_counter()
    image, crop_box, crop_size = preview_image(path, params, max_size)
    elapsed_ms = round((time.perf_counter() - start) * 1000)
    return jsonify(
        {
            "image": data_url(image),
            "elapsedMs": elapsed_ms,
            "size": [image.width, image.height],
            "cropBox": crop_box,
            "cropSize": crop_size,
        }
    )


@app.post("/api/save")
def save_current():
    payload = request.get_json(force=True)
    name = payload.get("image")
    params = params_from_dict(payload.get("params", {}))
    source = safe_image_path(name, ORIGINAL_DIR)
    destination = OUTPUT_DIR / name
    process_image(source, destination, params)

    saved = load_saved_params()
    saved[name] = asdict(params)
    write_saved_params(saved)
    return jsonify({"ok": True, "saved": saved, "output": f"/output/{name}"})


@app.post("/api/save-painted")
def save_painted():
    payload = request.get_json(force=True)
    name = payload.get("image")
    params = params_from_dict(payload.get("params", {}))
    source = safe_image_path(name, ORIGINAL_DIR)
    crop_box = payload.get("cropBox")
    preview_size = payload.get("previewSize")
    strokes = payload.get("strokes", [])
    if not crop_box or not preview_size:
        abort(400, "Missing cropBox or previewSize")

    image = render_sticker(source, params)
    image = apply_manual_strokes(image, strokes, crop_box, preview_size)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT_DIR / name, optimize=True)

    saved = load_saved_params()
    saved[name] = asdict(params)
    write_saved_params(saved)
    return jsonify({"ok": True, "saved": saved, "output": f"/output/{name}"})


@app.post("/api/save-params")
def save_params_only():
    payload = request.get_json(force=True)
    name = payload.get("image")
    safe_image_path(name, ORIGINAL_DIR)
    params = params_from_dict(payload.get("params", {}))
    saved = load_saved_params()
    saved[name] = asdict(params)
    write_saved_params(saved)
    return jsonify({"ok": True, "saved": saved})


@app.post("/api/render-all")
def render_all():
    payload = request.get_json(force=True)
    mode = payload.get("mode", "current")
    current = params_from_dict(payload.get("params", {}))
    saved = load_saved_params()
    rendered = []

    for name in image_names():
        params = current
        if mode == "saved" and name in saved:
            params = params_from_dict(saved[name])
        process_image(ORIGINAL_DIR / name, OUTPUT_DIR / name, params)
        rendered.append(name)

    return jsonify({"ok": True, "rendered": rendered})


def main() -> None:
    host = os.environ.get("STICKER_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("STICKER_WEB_PORT", "5057"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
