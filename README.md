# Sticker Cutout Tuner

Turn white-background meme sticker sheets into transparent PNG stickers with a local, tunable workflow.

This project combines:

- a parameterized OpenCV/Pillow processing pipeline in `process_stickers.py`
- a local Flask UI in `web_app.py` for previewing, tuning, and saving results
- optional manual paint/erase cleanup for tiny edge defects after automatic extraction

The repository now includes one published sample pair for reference:

- input: [`original/hug.png`](original/hug.png)
- output: [`output/hug.png`](output/hug.png)
- saved tuning example: [`sticker_params.example.json`](sticker_params.example.json)

The repository is set up for open-source sharing: source images and generated outputs stay local, while the code, docs, and project metadata are ready to publish.

## Features

- Remove page background and rebuild a clean sticker backing
- Generate a soft synthetic shadow instead of preserving noisy original edges
- Tune per-image parameters from a browser UI
- Save per-image settings for repeatable batch renders
- Manually patch small gaps with white brush, eraser, or area delete tools
- Batch-render all stickers from the CLI or web UI
- Keep local assets out of Git while preserving the expected folder layout
- Ship one sample input/output pair so GitHub visitors can see the workflow immediately

## Sample input/output

<table>
  <tr>
    <th>Input sticker sheet</th>
    <th>Rendered output</th>
  </tr>
  <tr>
    <td><img src="original/hug.png" alt="Sample source sticker sheet" width="280"></td>
    <td><img src="output/hug.png" alt="Sample transparent sticker output" width="280"></td>
  </tr>
</table>

You can reproduce the sample render with the checked-in example params:

```zsh
python process_stickers.py --input original --output output --image hug.png --params-json sticker_params.example.json --use-saved
```

## How it works

The extraction pipeline is designed for a specific hard case: the page background, old sticker backing, and old shadow are all visually similar. A simple white-pixel removal step is not enough.

At a high level, the pipeline:

1. Estimates the background color from the image border.
2. Detects strong foreground anchors from saturation, value, texture, and contrast.
3. Expands into adjacent pixels to retain shapes, text, and small symbols.
4. Splits the result into a **content mask** and a rebuilt **backing mask**.
5. Smooths the backing mask, feathers both masks, and adds one synthetic shadow.
6. Writes the final RGBA PNG.

For more detail, see [`docs/algorithm-notes.md`](docs/algorithm-notes.md).

## Repository layout
```text
.
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── process_stickers.py      # CLI/batch renderer
├── web_app.py               # Local Flask tuning UI
├── .github/
│   └── workflows/
│       └── release.yml      # Semantic release on pushes to main
├── docs/
│   └── algorithm-notes.md
├── original/
│   ├── README.md
│   └── hug.png              # Published sample source image
├── output/
│   ├── README.md
│   └── hug.png              # Published sample rendered result
├── static/
│   ├── app.js
│   └── styles.css
├── templates/
│   └── index.html
└── tests/
    └── test_process_stickers.py
```

## Requirements

- Python 3.9+
- macOS, Linux, or Windows
- PNG source images placed in `original/`

## Quick start

### 1. Create a virtual environment

```zsh
cd sticker-cutout-tuner
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Add source images

The repo already includes one sample source file at `original/hug.png` so you can inspect the workflow immediately. Add your own sticker-sheet PNGs into `original/` as needed.

Expected input characteristics:

- PNG files
- mostly white page background
- sticker art already present on the sheet
- original sticker backing/shadow may still be visible

### 3. Start the web UI

```zsh
python web_app.py
```

Then open <http://127.0.0.1:5057>.

### 4. Or render from the command line

Render every PNG in `original/` to `output/`:

```zsh
python process_stickers.py --input original --output output
```

Render a single image:

```zsh
python process_stickers.py --input original --output output --image morning.png
```

Render the published sample image using the published sample saved params:

```zsh
python process_stickers.py --input original --output output --image hug.png --params-json sticker_params.example.json --use-saved
```

Render using previously saved per-image settings:

```zsh
python process_stickers.py --input original --output output --params-json sticker_params.json --use-saved
```

If you want to start from the checked-in example, copy it first:

```zsh
cp sticker_params.example.json sticker_params.json
```

## Web UI workflow

1. Select an image from the left rail.
2. Start with **Common Fixes** presets and quick controls.
3. Use the advanced controls only when needed.
4. Preview on checker, dark, or white backgrounds.
5. Use manual brush tools for tiny cleanup after parameter tuning.
6. Save the image or save params only.
7. Batch-render all images with the current settings or each image's saved settings.

### Manual tools

- **Paint White**: fill tiny transparent gaps
- **Eraser**: remove unwanted fragments back to transparency
- **Area Delete**: flood-fill delete a connected region near the click point

## Configuration

The web app supports optional environment variables so you can keep local data outside the repository if you want:

- `STICKER_INPUT_DIR` — source image directory
- `STICKER_OUTPUT_DIR` — rendered image directory
- `STICKER_PARAMS_PATH` — saved parameter JSON path
- `STICKER_WEB_HOST` — Flask host, default `127.0.0.1`
- `STICKER_WEB_PORT` — Flask port, default `5057`

Example:

```zsh
STICKER_INPUT_DIR=~/stickers/in \
STICKER_OUTPUT_DIR=~/stickers/out \
STICKER_PARAMS_PATH=~/stickers/sticker_params.json \
python web_app.py
```

## Development

Install the project in editable mode:

```zsh
pip install -e .
```

Install the extra release tooling locally when you want to dry-run or inspect semantic-release behavior:

```zsh
pip install -e '.[release]'
```

This also exposes console scripts:

```zsh
sticker-cutout --input original --output output
sticker-cutout-web
```

Run the smoke tests:

```zsh
python -m unittest discover -s tests -v
```

## Automated releases

This repository is configured for automated semantic releases through GitHub Actions.

- The workflow file is `.github/workflows/release.yml`
- Releases run automatically on pushes to the `main` branch
- The workflow runs the test suite before creating a release
- `python-semantic-release` updates `project.version` in `pyproject.toml`, tags the release, updates `CHANGELOG.md`, and creates a GitHub Release

### Commit message convention

Use Conventional Commit-style messages so release bumps are calculated correctly:

- `feat: add batch preset picker` → minor release
- `fix: preserve tiny text symbols in output` → patch release
- `perf: speed up preview rendering` → patch release
- `docs: improve README setup section` → no release by default
- `feat!: change preview API payload` or a `BREAKING CHANGE:` footer → breaking release

### GitHub repository setting required

In the GitHub repository, make sure **Settings → Actions → General → Workflow permissions** is set to **Read and write permissions** so the workflow can push the release commit/tag and publish the GitHub Release.

### Optional local dry run

```zsh
pip install -e '.[release]'
semantic-release version --noop
```

## Notes for publishing

- The repository intentionally keeps most source PNGs and generated outputs local, but it does publish one reference pair: [`original/hug.png`](original/hug.png) and [`output/hug.png`](output/hug.png).
- The repository ships [`sticker_params.example.json`](sticker_params.example.json) as a concise sample for that published image; the live `sticker_params.json` file is meant to stay local and is ignored by Git.
- If you want to ship sample assets later, make sure you have the rights to redistribute them.

## License

This repository is released under the MIT License. See [`LICENSE`](LICENSE).

User-provided source images and generated outputs are not included in the repository and are not automatically covered by this project license unless you choose to license them separately.
