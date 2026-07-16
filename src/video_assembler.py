"""Phase 1 video assembly: keyframes plus readable story text, nothing else."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, concatenate_videoclips

from font_utils import cjk_font_candidates


ROOT = Path(__file__).resolve().parent.parent


class BasicVideoAssembler:
    """Create a deterministic MP4 baseline without animation, effects, or audio."""

    def __init__(self, width: int = 1080, height: int = 1440, fps: int = 24):
        self.width = width
        self.height = height
        self.fps = fps

    @staticmethod
    def load_scenes(path: Path) -> List[Dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        scenes = data if isinstance(data, list) else data.get("scenes", [])
        if not isinstance(scenes, list) or not scenes:
            raise ValueError(f"场景文件没有有效 scenes 列表：{path}")
        return scenes

    @staticmethod
    def find_keyframe(keyframes_dir: Path, scene_id: int) -> Path:
        for suffix in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = keyframes_dir / f"scene_{scene_id:02d}{suffix}"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"缺少场景 {scene_id:02d} 的关键帧")

    def validate_assets(self, scenes: Sequence[Dict[str, Any]], keyframes_dir: Path) -> List[Path]:
        if not keyframes_dir.exists():
            raise FileNotFoundError(f"关键帧目录不存在：{keyframes_dir}")
        paths = []
        for expected_id, scene in enumerate(scenes, 1):
            scene_id = int(scene.get("id", expected_id))
            paths.append(self.find_keyframe(keyframes_dir, scene_id))
            duration = scene.get("duration", 4.5)
            if not isinstance(duration, (int, float)) or not 2.0 <= float(duration) <= 8.0:
                raise ValueError(f"场景 {scene_id:02d} 的 duration 必须在 2–8 秒之间")
        return paths

    @staticmethod
    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        for path in cjk_font_candidates(ROOT):
            if path.exists():
                return ImageFont.truetype(str(path), size)
        return ImageFont.load_default(size=size)

    @staticmethod
    def _fit_cover(image: Image.Image, width: int, height: int) -> Image.Image:
        scale = max(width / image.width, height / image.height)
        size = (round(image.width * scale), round(image.height * scale))
        resized = image.resize(size, Image.Resampling.LANCZOS)
        left = max(0, (resized.width - width) // 2)
        top = max(0, (resized.height - height) // 2)
        return resized.crop((left, top, left + width, top + height))

    @staticmethod
    def _wrap_text(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw, max_width: int) -> List[str]:
        text = re.sub(r"\s+", "", text.strip())
        if not text:
            return []
        lines, current = [], ""
        for char in text:
            candidate = current + char
            if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def render_scene(self, keyframe: Path, text: str) -> np.ndarray:
        with Image.open(keyframe) as source:
            image = self._fit_cover(source.convert("RGB"), self.width, self.height).convert("RGBA")
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = self._load_font(42)
        lines = self._wrap_text(text, font, draw, self.width - 180)[:3]
        if lines:
            line_height = 58
            box_height = 42 + line_height * len(lines)
            top = self.height - box_height - 70
            draw.rounded_rectangle(
                (65, top, self.width - 65, self.height - 55), radius=24,
                fill=(255, 252, 244, 210), outline=(75, 65, 55, 55), width=2,
            )
            y = top + 22
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                x = (self.width - (bbox[2] - bbox[0])) // 2
                draw.text((x + 1, y + 1), line, font=font, fill=(255, 255, 255, 100))
                draw.text((x, y), line, font=font, fill=(48, 43, 38, 235))
                y += line_height
        return np.asarray(Image.alpha_composite(image, overlay).convert("RGB"))

    def assemble(
        self,
        scenes: Sequence[Dict[str, Any]],
        keyframes_dir: Path,
        output_path: Path,
    ) -> Path:
        keyframes = self.validate_assets(scenes, keyframes_dir)
        clips = []
        try:
            for scene, keyframe in zip(scenes, keyframes):
                frame = self.render_scene(keyframe, str(scene.get("on_screen_text", "")))
                clips.append(ImageClip(frame).with_duration(float(scene.get("duration", 4.5))))
            video = concatenate_videoclips(clips, method="compose")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            video.write_videofile(
                str(output_path), fps=self.fps, codec="libx264", audio=False,
                preset="medium", ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
            )
            video.close()
        finally:
            for clip in clips:
                clip.close()
        return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1：关键帧＋文字基础视频合成")
    parser.add_argument("--scenes", type=Path, default=ROOT / "output" / "scenes_with_prompts.json")
    parser.add_argument("--keyframes", type=Path, default=ROOT / "assets" / "keyframes")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "phase1_baseline.mp4")
    parser.add_argument("--fps", type=int, default=24)
    args = parser.parse_args()
    assembler = BasicVideoAssembler(fps=args.fps)
    scenes = assembler.load_scenes(args.scenes)
    result = assembler.assemble(scenes, args.keyframes, args.output)
    print(f"Phase 1 基线视频已生成：{result}")


if __name__ == "__main__":
    main()
