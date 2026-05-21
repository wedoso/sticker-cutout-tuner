import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from process_stickers import StickerParams, params_from_dict, render_sticker


class ProcessStickersSmokeTests(unittest.TestCase):
    def make_source_image(self, path: Path) -> None:
        image = Image.new("RGB", (320, 320), "white")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((60, 70, 250, 270), radius=48, fill=(244, 90, 90))
        draw.ellipse((100, 115, 150, 165), fill=(35, 35, 35))
        draw.ellipse((175, 115, 225, 165), fill=(35, 35, 35))
        draw.arc((110, 130, 215, 225), 20, 160, fill=(35, 35, 35), width=8)
        draw.rectangle((240, 235, 285, 280), fill=(255, 210, 70))
        image.save(path)

    def test_params_from_dict_coerces_types(self):
        params = params_from_dict({"outline_px": 9.8, "edge_smooth_px": 4})
        self.assertIsInstance(params, StickerParams)
        self.assertEqual(params.outline_px, 10)
        self.assertEqual(params.edge_smooth_px, 4.0)

    def test_render_sticker_returns_rgba_with_transparency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "synthetic.png"
            self.make_source_image(source)

            result = render_sticker(source)
            array = np.array(result)

            self.assertEqual(result.mode, "RGBA")
            self.assertEqual(result.size, (320, 320))
            self.assertTrue(np.any(array[:, :, 3] == 0))
            self.assertTrue(np.any(array[:, :, 3] > 0))

    def test_cli_renders_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "in"
            output_dir = root / "out"
            input_dir.mkdir()
            source = input_dir / "synthetic.png"
            self.make_source_image(source)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "process_stickers.py"),
                    "--input",
                    str(input_dir),
                    "--output",
                    str(output_dir),
                    "--image",
                    source.name,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            output_file = output_dir / source.name
            self.assertTrue(output_file.exists())
            self.assertIn(source.name, completed.stdout)


if __name__ == "__main__":
    unittest.main()

