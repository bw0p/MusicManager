from PIL import Image
from pathlib import Path

source = Path("assets/512Icon.png")
output_dir = Path("assets")
output_dir.mkdir(exist_ok=True)

img = Image.open(source).convert("RGBA")

img.save(
    output_dir / "app_icon.ico",
    sizes=[
        (16, 16),
        (24, 24),
        (32, 32),
        (48, 48),
        (64, 64),
        (128, 128),
        (256, 256),
    ],
)