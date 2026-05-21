# Algorithm and Tuning Notes

## Project Goal

Create transparent-background sticker PNGs from white-background meme images in `original/`, writing finished files to `output/`.

## Quality Requirements

- Preserve the full sticker content: character, Chinese text, punctuation, hearts, stars, and small symbols.
- Do not use a simple "delete white pixels" approach, because the original white sticker backing is visually close to the page background.
- Avoid preserving both old and new sticker edges. The current preferred strategy is to remove the source backing/shadow first, then rebuild one clean white backing and one soft shadow.
- Edges must be rounded and smooth. Obvious jagged fragments or double bottom edges are unacceptable.
- Per-image tuning is required. `pity.png` looks good with the current defaults, while `morning.png` and `hug.png` need different settings because their bottom backing/shadow forms a visible double edge.

## Processing Model

The pipeline is parameterized:

1. Detect strong foreground anchors from color, darkness, and high contrast.
2. Expand from anchors into adjacent shape pixels to preserve small symbols and text.
3. Split the mask into:
   - content mask: real art pixels that get composited from the source image.
   - backing mask: a fresh white sticker base generated around the content/shape.
4. Smooth and feather the backing mask.
5. Add one synthetic shadow behind the backing.
6. Output RGBA PNG.

`rembg` was tested as a helper, but it dropped or dimmed text/symbols, so it is not the primary method.

## Main Tunable Parameters

- `outline_px`: width of the rebuilt white sticker backing.
- `edge_smooth_px`: Gaussian smoothing applied to the backing mask before alpha generation.
- `backing_feather_px`: softness of the outer white backing edge.
- `content_feather_px`: softness of the source art mask.
- `shadow_blur_px`: blur radius of the generated shadow.
- `shadow_opacity`: maximum alpha of the generated shadow.
- `shadow_offset_x`, `shadow_offset_y`: generated shadow offset.
- `min_body_area`: area threshold used to decide which connected component is the main character/body region.
- `shape_*`: thresholds for pixels allowed to influence the backing shape.
- `art_*`: thresholds for pixels copied from the source image into the final sticker.
- `neutral_*`: controls light neutral texture retention, mainly useful for white clothing details.
- `adjacent_*`: controls how much soft/nearby edge material is pulled into the backing shape.

## Web App Behavior

- Select any PNG from `original/`.
- Preview the current parameter set on checker, dark, or white background.
- The primary UI should expose only a small set of practical controls: outline width, old-edge cleanup, edge roundness, shadow strength, shadow softness, and art-edge softness.
- Advanced threshold controls can exist, but they should be collapsed by default.
- Include a preset for double-edge cases like `morning.png` and `hug.png`.
- Include a manual white brush correction layer for tiny transparent gaps after parameter tuning.
- Brush corrections should save into the full-resolution output image, not only the preview.
- Save the current image to `output/`.
- Store per-image parameter choices in `sticker_params.json`.
- Batch render all images with either the current parameter set or each image's saved parameter set.

## Practical Tuning Guidance

- Double bottom edge: first apply `Fix Double Edge`, then reduce `Outline`, increase `Old Edge Cleanup`, increase `Edge Roundness`, and reduce `Shadow Strength`.
- Lost small text/symbols: lower `Old Edge Cleanup` or use `Preserve Detail`.
- Jagged edge: increase `Edge Roundness` and `Art Edge Softness`.
- Heavy outline: reduce `Outline`.
- Two shadows: reduce `Shadow Strength` or use `Light Shadow`.

