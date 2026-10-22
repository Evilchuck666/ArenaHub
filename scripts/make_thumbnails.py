"""Make the map thumbnails shown in the Maps tab from the levelshots inside assets/maps.

Run after adding a map pack:  uv run python scripts/make_thumbnails.py
"""

import sys
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage

from arenahub.core import maps

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZE = (maps.THUMBNAIL_SIZE[0] * 2, maps.THUMBNAIL_SIZE[1] * 2)  # sharp on HiDPI screens

# Some old .pk3 files carry malformed extra fields that the engine ignores but
# zipfile rejects; only the member names and data are needed here.
zipfile.ZipInfo._decodeExtra = lambda self, *args: None

# Qt only reads .tga files that end with the TGA 2.0 footer, which many
# levelshots lack; without extension or developer areas it is just this.
TGA_FOOTER = b"\0" * 8 + b"TRUEVISION-XFILE.\0"


def levelshot(pack: maps.MapPack) -> QImage | None:
    """The first map's levelshot, preferring .tga like the engine does."""
    with zipfile.ZipFile(ASSETS / "maps" / pack.filename) as zf:
        names = {name.lower(): name for name in zf.namelist()}
        for ext in ("tga", "jpg", "jpeg", "png"):
            if name := names.get(f"levelshots/{pack.maps[0]}.{ext}"):
                data = zf.read(name)
                if ext == "tga" and not data.endswith(TGA_FOOTER[8:]):
                    data += TGA_FOOTER
                image = QImage()
                if image.loadFromData(data):
                    return image
    return None


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841 - image plugins need an application
    out_dir = ASSETS / "levelshots"
    out_dir.mkdir(exist_ok=True)
    failed = 0
    for pack in maps.MAPS:
        image = levelshot(pack)
        if image is None:
            print(f"No levelshot for {pack.maps[0]} in {pack.filename}", file=sys.stderr)
            failed += 1
            continue
        # The game always shows levelshots at 4:3, whatever their real size.
        thumb = image.scaled(
            *SIZE, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        dest = out_dir / maps.thumbnail_name(pack)
        if not thumb.convertToFormat(QImage.Format.Format_RGB32).save(str(dest), "JPG", 85):
            print(f"Could not write {dest}", file=sys.stderr)
            return 1
        print(f"Wrote {dest}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
