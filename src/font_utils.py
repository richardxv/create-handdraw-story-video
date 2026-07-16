"""Cross-platform font discovery for CJK video captions."""

from __future__ import annotations

import os
import platform
from pathlib import Path


def cjk_font_candidates(project_root: Path) -> list[Path]:
    candidates = [
        project_root / "assets" / "fonts" / "handwrite.ttf",
        project_root / "assets" / "fonts" / "handwrite.otf",
    ]
    system = platform.system()
    if system == "Windows":
        windows_dir = os.environ.get("WINDIR")
        if windows_dir:
            fonts = Path(windows_dir) / "Fonts"
            candidates.extend((fonts / "simkai.ttf", fonts / "simfang.ttf", fonts / "msyh.ttc"))
    elif system == "Darwin":
        candidates.extend((Path("/System/Library/Fonts/PingFang.ttc"), Path("/System/Library/Fonts/STHeiti Medium.ttc")))
    else:
        candidates.extend((
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        ))
    return candidates
