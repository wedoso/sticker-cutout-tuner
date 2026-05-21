#!/usr/bin/env python3
"""Parameterized sticker background removal.

The source images are memes on a white page. The page, the original sticker
backing, and the old shadow are visually close to each other, so a single
global threshold is not enough. This module exposes the main cutout parameters
so they can be tuned per image from the local web app.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi


@dataclass
class StickerParams:
    outline_px: int = 12
    edge_smooth_px: float = 3.2
    backing_feather_px: float = 1.5
    content_feather_px: float = 1.0
    shadow_blur_px: float = 6.5
    shadow_opacity: int = 42
    shadow_offset_x: int = 3
    shadow_offset_y: int = 4
    min_body_area: int = 120000
    shape_close_px: int = 2
    backing_min_area: int = 180
    body_texture: float = 1.0
    art_saturation_min: float = 10.0
    art_diff_min: float = 8.0
    art_dark_value_max: float = 216.0
    art_dark_diff_min: float = 14.0
    art_strong_diff: float = 72.0
    shape_saturation_min: float = 8.0
    shape_diff_min: float = 8.0
    shape_dark_value_max: float = 240.0
    shape_dark_diff_min: float = 22.0
    shape_gradient_min: float = 4.0
    shape_strong_diff: float = 55.0
    adjacent_radius_px: int = 2
    adjacent_saturation_min: float = 4.0
    adjacent_diff_min: float = 7.0
    adjacent_dark_value_max: float = 248.0
    adjacent_dark_diff_min: float = 16.0
    adjacent_gradient_min: float = 5.0
    neutral_saturation_max: float = 12.0
    neutral_value_max: float = 248.0
    neutral_diff_min: float = 12.0
    neutral_gradient_min: float = 8.0
    anchor_saturation_min: float = 18.0
    anchor_diff_min: float = 10.0
    anchor_dark_value_max: float = 215.0
    anchor_dark_diff_min: float = 14.0
    anchor_strong_diff: float = 75.0


DEFAULT_PARAMS = StickerParams()
PARAM_NAMES = {field.name for field in fields(StickerParams)}


def params_from_dict(data: dict | None) -> StickerParams:
    if not data:
        return StickerParams()

    values = asdict(DEFAULT_PARAMS)
    for field in fields(StickerParams):
        if field.name not in data:
            continue
        value = data[field.name]
        default = getattr(DEFAULT_PARAMS, field.name)
        if isinstance(default, int):
            values[field.name] = int(round(float(value)))
        else:
            values[field.name] = float(value)
    return StickerParams(**values)


def ellipse(radius: int) -> np.ndarray:
    radius = max(1, int(radius))
    return cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1)
    )


def estimate_background(rgb: np.ndarray) -> np.ndarray:
    height, width, _ = rgb.shape
    border_width = max(12, min(height, width) // 35)
    border = np.concatenate(
        [
            rgb[:border_width].reshape(-1, 3),
            rgb[-border_width:].reshape(-1, 3),
            rgb[:, :border_width].reshape(-1, 3),
            rgb[:, -border_width:].reshape(-1, 3),
        ]
    )
    return np.median(border, axis=0).astype(np.float32)


def keep_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), 8
    )
    kept = np.zeros(mask.shape, dtype=bool)
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            kept[labels == label] = True
    return kept


def keep_components_touching_anchor(
    candidate: np.ndarray, anchor: np.ndarray, min_area: int
) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        candidate.astype(np.uint8), 8
    )
    kept = np.zeros(candidate.shape, dtype=bool)
    anchor = anchor.astype(bool)
    for label in range(1, count):
        component = labels == label
        if (
            stats[label, cv2.CC_STAT_AREA] >= min_area
            and np.any(anchor[component])
        ):
            kept[component] = True
    return kept


def large_component_region(mask: np.ndarray, min_area: int) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), 8
    )
    region = np.zeros(mask.shape, dtype=bool)
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            region[labels == label] = True
    return region


def signed_distance_alpha(mask: np.ndarray, feather_px: float) -> np.ndarray:
    hard = mask.astype(np.uint8)
    inside = cv2.distanceTransform(hard, cv2.DIST_L2, 5)
    outside = cv2.distanceTransform(1 - hard, cv2.DIST_L2, 5)
    alpha = np.clip((inside - outside + feather_px) / (2 * feather_px), 0, 1)
    alpha = (alpha * 255).astype(np.uint8)
    alpha = np.where(alpha > 250, 255, alpha)
    alpha = np.where(alpha < 2, 0, alpha)
    return alpha.astype(np.uint8)


def smooth_mask(mask: np.ndarray, sigma: float, threshold: float = 0.5) -> np.ndarray:
    blurred = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigma)
    return blurred > threshold


def shifted_mask(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    height, width = mask.shape
    shifted = np.zeros_like(mask, dtype=np.uint8)

    dst_y0 = max(0, dy)
    dst_y1 = height + min(0, dy)
    dst_x0 = max(0, dx)
    dst_x1 = width + min(0, dx)

    src_y0 = max(0, -dy)
    src_y1 = height - max(0, dy)
    src_x0 = max(0, -dx)
    src_x1 = width - max(0, dx)

    shifted[dst_y0:dst_y1, dst_x0:dst_x1] = mask[src_y0:src_y1, src_x0:src_x1]
    return shifted


def alpha_composite_over(
    base_rgb: np.ndarray,
    base_alpha: np.ndarray,
    top_rgb: np.ndarray,
    top_alpha: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    top = top_alpha.astype(np.float32) / 255.0
    active = top > 0
    if not np.any(active):
        return base_rgb, base_alpha

    previous = base_alpha[active].astype(np.float32) / 255.0
    new_alpha = top[active] + previous * (1 - top[active])
    composed = (
        top_rgb[active].astype(np.float32) * top[active, None]
        + base_rgb[active].astype(np.float32)
        * previous[:, None]
        * (1 - top[active, None])
    )
    base_rgb[active] = np.where(
        new_alpha[:, None] > 0, composed / new_alpha[:, None], 0
    ).astype(np.uint8)
    base_alpha[active] = (new_alpha * 255).astype(np.uint8)
    return base_rgb, base_alpha


def build_masks(rgb: np.ndarray, params: StickerParams) -> tuple[np.ndarray, np.ndarray]:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1].astype(np.float32)
    value = hsv[:, :, 2].astype(np.float32)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(grad_x, grad_y)

    background = estimate_background(rgb)
    diff = np.max(np.abs(rgb.astype(np.float32) - background), axis=2)

    anchor = (
        ((saturation > params.anchor_saturation_min) & (diff > params.anchor_diff_min))
        | ((value < params.anchor_dark_value_max) & (diff > params.anchor_dark_diff_min))
        | (diff > params.anchor_strong_diff)
    )

    neutral_texture = (
        (saturation <= params.neutral_saturation_max)
        & (value < params.neutral_value_max)
        & (diff > params.neutral_diff_min)
        & (gradient > params.neutral_gradient_min)
    )

    candidate = (
        ((saturation > params.shape_saturation_min) & (diff > params.shape_diff_min))
        | (
            (value < params.shape_dark_value_max)
            & (diff > params.shape_dark_diff_min)
            & (gradient > params.shape_gradient_min)
        )
        | (diff > params.shape_strong_diff)
        | neutral_texture
    )
    candidate = cv2.morphologyEx(
        candidate.astype(np.uint8), cv2.MORPH_CLOSE, ellipse(1), iterations=1
    ).astype(bool)

    shape_seed = keep_components_touching_anchor(
        candidate,
        cv2.dilate(
            anchor.astype(np.uint8), ellipse(params.adjacent_radius_px), iterations=1
        ).astype(bool),
        min_area=10,
    )
    adjacent_shape = (
        (
            ((saturation > params.adjacent_saturation_min) & (diff > params.adjacent_diff_min))
            | (
                (value < params.adjacent_dark_value_max)
                & (diff > params.adjacent_dark_diff_min)
                & (gradient > params.adjacent_gradient_min)
            )
        )
        & cv2.dilate(
            shape_seed.astype(np.uint8),
            ellipse(params.adjacent_radius_px),
            iterations=1,
        ).astype(bool)
    )
    shape_seed = keep_components(shape_seed | adjacent_shape, min_area=18)
    shape_seed = cv2.morphologyEx(
        shape_seed.astype(np.uint8),
        cv2.MORPH_CLOSE,
        ellipse(params.shape_close_px),
        iterations=1,
    ).astype(bool)

    body_region = large_component_region(shape_seed, min_area=params.min_body_area)
    primary_art = (
        ((saturation > params.art_saturation_min) & (diff > params.art_diff_min))
        | ((value < params.art_dark_value_max) & (diff > params.art_dark_diff_min))
        | (diff > params.art_strong_diff)
    )
    content = shape_seed & (
        primary_art | (neutral_texture & body_region & (params.body_texture > 0))
    )
    content = keep_components(content, min_area=8)
    content = cv2.morphologyEx(
        content.astype(np.uint8), cv2.MORPH_CLOSE, ellipse(1), iterations=1
    ).astype(bool)

    backing = cv2.dilate(
        shape_seed.astype(np.uint8), ellipse(params.outline_px), iterations=1
    )
    backing = cv2.morphologyEx(
        backing,
        cv2.MORPH_CLOSE,
        ellipse(max(3, params.outline_px // 3)),
        iterations=1,
    ).astype(bool)
    backing = ndi.binary_fill_holes(backing)
    backing = keep_components(backing, min_area=params.backing_min_area)
    backing = smooth_mask(backing, sigma=params.edge_smooth_px)
    backing = cv2.morphologyEx(
        backing.astype(np.uint8), cv2.MORPH_OPEN, ellipse(1), iterations=1
    ).astype(bool)
    backing = cv2.morphologyEx(
        backing.astype(np.uint8), cv2.MORPH_CLOSE, ellipse(2), iterations=1
    ).astype(bool)
    backing = ndi.binary_fill_holes(backing)

    return content, backing


def render_sticker(source: Path, params: StickerParams | None = None) -> Image.Image:
    params = params or StickerParams()
    rgb = np.array(Image.open(source).convert("RGB"))
    content, backing = build_masks(rgb, params)

    backing_alpha = signed_distance_alpha(backing, feather_px=params.backing_feather_px)
    content_alpha = signed_distance_alpha(content, feather_px=params.content_feather_px)

    hard_backing = backing.astype(np.uint8)
    shadow = shifted_mask(
        hard_backing, dx=params.shadow_offset_x, dy=params.shadow_offset_y
    ).astype(np.float32)
    shadow = cv2.GaussianBlur(shadow, (0, 0), params.shadow_blur_px)
    shadow_alpha = np.clip(
        shadow * params.shadow_opacity, 0, params.shadow_opacity
    ).astype(np.uint8)
    shadow_alpha = np.where(hard_backing > 0, 0, shadow_alpha).astype(np.uint8)

    output_rgb = np.zeros_like(rgb)
    output_alpha = shadow_alpha.copy()

    backing_pixels = backing_alpha > 0
    output_rgb[backing_pixels] = 255
    output_alpha[backing_pixels] = backing_alpha[backing_pixels]

    output_rgb, output_alpha = alpha_composite_over(
        output_rgb, output_alpha, rgb, content_alpha
    )
    return Image.fromarray(np.dstack([output_rgb, output_alpha]))


def process_image(
    source: Path,
    destination: Path,
    params: StickerParams | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    render_sticker(source, params).save(destination, optimize=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove white backgrounds and rebuild clean sticker backing."
    )
    parser.add_argument("--input", default="original", type=Path)
    parser.add_argument("--output", default="output", type=Path)
    parser.add_argument("--params-json", default=None, type=Path)
    parser.add_argument("--use-saved", action="store_true")
    parser.add_argument("--image", default=None)
    for field in fields(StickerParams):
        default = getattr(DEFAULT_PARAMS, field.name)
        value_type = int if isinstance(default, int) else float
        parser.add_argument(
            "--" + field.name.replace("_", "-"),
            dest=field.name,
            default=None,
            type=value_type,
        )
    return parser.parse_args()


def load_saved_params(path: Path | None) -> dict[str, dict]:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text())


def params_from_args(args: argparse.Namespace) -> StickerParams:
    values = {}
    for name in PARAM_NAMES:
        value = getattr(args, name)
        if value is not None:
            values[name] = value
    return params_from_dict(values)


def main() -> None:
    args = parse_args()
    saved = load_saved_params(args.params_json)
    base_params = params_from_args(args)

    sources = sorted(args.input.glob("*.png"))
    if args.image:
        sources = [args.input / args.image]
    if not sources:
        raise SystemExit(f"No PNG files found in {args.input}")

    for source in sources:
        if not source.exists():
            raise SystemExit(f"Missing source image: {source}")
        params = base_params
        if args.use_saved and source.name in saved:
            params = params_from_dict(saved[source.name])
        destination = args.output / source.name
        process_image(source, destination, params)
        print(f"{source} -> {destination}")


if __name__ == "__main__":
    main()
