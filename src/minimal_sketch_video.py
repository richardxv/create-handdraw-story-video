"""Minimal white-paper sketch video mode inspired by hand-drawn explainer videos."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from moviepy import VideoClip, concatenate_videoclips

from font_utils import cjk_font_candidates


ROOT = Path(__file__).resolve().parent.parent


class MinimalSketchVideoAssembler:
    """Render story scenes as progressively drawn black ink on warm white paper."""

    def __init__(self, width: int = 1080, height: int = 1440, fps: int = 12):
        self.width = width
        self.height = height
        self.fps = fps
        self.paper = (252, 250, 244)
        self.font = self._load_font(50)

    @staticmethod
    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        for path in cjk_font_candidates(ROOT):
            if path.exists():
                return ImageFont.truetype(str(path), size)
        return ImageFont.load_default(size=size)

    @staticmethod
    def load_scenes(path: Path) -> List[Dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        scenes = data if isinstance(data, list) else data.get("scenes", [])
        if not scenes:
            raise ValueError(f"场景文件没有有效 scenes：{path}")
        return scenes

    @staticmethod
    def find_keyframe(directory: Path, scene_id: int) -> Path:
        for suffix in (".png", ".jpg", ".jpeg", ".webp"):
            path = directory / f"scene_{scene_id:02d}{suffix}"
            if path.exists():
                return path
        raise FileNotFoundError(f"缺少场景 {scene_id:02d} 的关键帧")

    def _wrap_text(self, text: str, max_chars: int = 16) -> List[str]:
        clean = "".join(text.split()).strip("。")
        if len(clean) <= max_chars:
            return [clean]
        lines = []
        while clean and len(lines) < 3:
            if len(clean) <= max_chars:
                lines.append(clean)
                break
            cut = max_chars
            for index in range(max_chars, max(7, max_chars - 6), -1):
                if clean[index - 1] in "，。！？；":
                    cut = index
                    break
            lines.append(clean[:cut])
            clean = clean[cut:]
        if clean:
            lines[-1] += clean
        return lines

    def _make_line_art(self, source_path: Path) -> tuple[Image.Image, np.ndarray]:
        with Image.open(source_path) as source:
            source = source.convert("RGB")
            # Generated keyframes may contain signatures/model marks at the edge.
            # They are not story content, so exclude the bottom strip before tracing.
            crop_bottom = min(55, max(0, source.height // 16))
            if crop_bottom:
                source = source.crop((0, 0, source.width, source.height - crop_bottom))
            # Keep the whole composition and reserve generous white space around it.
            max_w, max_h = 840, 860
            scale = min(max_w / source.width, max_h / source.height)
            size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
            source = source.resize(size, Image.Resampling.LANCZOS)

        gray = ImageOps.grayscale(source).filter(ImageFilter.GaussianBlur(1.0))
        edge = gray.filter(ImageFilter.FIND_EDGES)
        edge = ImageOps.autocontrast(edge, cutoff=1)
        edge_array = np.asarray(edge, dtype=np.float32)
        # Retain confident contours and discard colored-pencil grain and stippling.
        alpha = np.clip((edge_array - 48.0) * 2.8, 0, 225).astype(np.uint8)
        # Remove hard image-frame borders introduced by edge detection.
        alpha[:4, :] = 0
        alpha[-4:, :] = 0
        alpha[:, :4] = 0
        alpha[:, -4:] = 0
        alpha_img = Image.fromarray(alpha)

        ink = Image.new("RGBA", size, (24, 23, 21, 0))
        ink.putalpha(alpha_img)

        # Strong structural contours arrive first; fine detail follows behind them.
        yy, xx = np.mgrid[0:size[1], 0:size[0]]
        rng = np.random.default_rng(abs(hash(source_path.name)) % (2**32))
        noise = rng.random((size[1], size[0]))
        strength = alpha.astype(np.float32) / 225.0
        order = (
            0.22 * (yy / max(1, size[1] - 1))
            + 0.10 * (xx / max(1, size[0] - 1))
            + 0.10 * noise
            + 0.58 * (1.0 - strength)
        )
        return ink, order.astype(np.float32)

    def _make_tonal_layers(
        self, source_path: Path, size: tuple[int, int]
    ) -> tuple[Image.Image, Image.Image, np.ndarray, np.ndarray]:
        """Create a soft monochrome underpainting and its watercolor colour layer."""
        with Image.open(source_path) as source:
            source = source.convert("RGB")
            crop_bottom = min(55, max(0, source.height // 16))
            if crop_bottom:
                source = source.crop((0, 0, source.width, source.height - crop_bottom))
            source = source.resize(size, Image.Resampling.LANCZOS)

        rgb = np.asarray(source, dtype=np.float32)
        gray_values = np.asarray(ImageOps.grayscale(source), dtype=np.float32)
        saturation = rgb.max(axis=2) - rgb.min(axis=2)
        # Avoid a visible rectangular image boundary: white/flat areas become paper.
        presence = np.clip(np.maximum((236.0 - gray_values) / 95.0, saturation / 90.0), 0.0, 1.0)
        presence = np.asarray(
            Image.fromarray((presence * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.3)),
            dtype=np.float32,
        ) / 255.0

        monochrome = ImageOps.colorize(
            Image.fromarray(gray_values.astype(np.uint8)), black=(45, 43, 40), white=self.paper
        ).convert("RGBA")
        monochrome.putalpha(Image.fromarray((presence * 185).astype(np.uint8)))

        # Lower saturation and translucency produce a gradual coloured-pencil wash.
        colour = Image.blend(ImageOps.grayscale(source).convert("RGB"), source, 0.72).convert("RGBA")
        colour.putalpha(Image.fromarray((presence * 205).astype(np.uint8)))

        yy, xx = np.mgrid[0:size[1], 0:size[0]]
        rng = np.random.default_rng((abs(hash(source_path.name)) + 17) % (2**32))
        noise = Image.fromarray((rng.random((size[1], size[0])) * 255).astype(np.uint8))
        noise = np.asarray(noise.filter(ImageFilter.GaussianBlur(24)), dtype=np.float32) / 255.0
        mono_order = 0.90 * (xx / max(1, size[0] - 1)) + 0.10 * noise
        colour_order = 0.52 * (xx / max(1, size[0] - 1)) + 0.18 * (yy / max(1, size[1] - 1)) + 0.30 * noise
        return monochrome, colour, mono_order.astype(np.float32), colour_order.astype(np.float32)

    def _render_text(self, text: str, progress: float) -> Image.Image:
        layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        lines = self._wrap_text(text)
        total_chars = sum(len(line) for line in lines)
        visible = max(0.0, min(float(total_chars), total_chars * progress))
        y = 195
        consumed = 0
        for line in lines:
            # Center the completed line once. Characters never shift as new ones appear.
            line_width = float(draw.textlength(line, font=self.font))
            x = max(85.0, (self.width - line_width) / 2.0)
            for index, char in enumerate(line):
                amount = visible - (consumed + index)
                if amount <= 0:
                    break
                fraction = min(1.0, amount)
                # Smoothstep removes the mechanical pop between adjacent characters.
                fraction = fraction * fraction * (3.0 - 2.0 * fraction)
                alpha = round(245 * fraction)
                char_x = x + float(draw.textlength(line[:index], font=self.font))
                draw.text((char_x, y), char, font=self.font, fill=(25, 24, 22, alpha))
            consumed += len(line)
            y += 68
        return layer

    def create_scene_clip(self, scene: Dict[str, Any], keyframe: Path) -> VideoClip:
        requested_duration = float(scene.get("duration", 4.5))
        text = str(scene.get("on_screen_text", ""))
        readable_chars = len("".join(text.split()))
        # Keep only a short reading hold after the reveal. Longer captions receive
        # a little extra time without forcing every scene to linger.
        paced_duration = min(3.55, max(2.75, 2.30 + readable_chars * 0.045))
        duration = min(requested_duration, paced_duration)
        ink, _ = self._make_line_art(keyframe)
        monochrome, colour, mono_order, colour_order = self._make_tonal_layers(keyframe, ink.size)
        monochrome_alpha = np.asarray(monochrome.getchannel("A"), dtype=np.uint8)
        colour_alpha = np.asarray(colour.getchannel("A"), dtype=np.uint8)
        x = (self.width - ink.width) // 2
        y = self.height - ink.height - 70

        def make_frame(t: float) -> np.ndarray:
            canvas = Image.new("RGBA", (self.width, self.height), (*self.paper, 255))
            # Begin as a shaded black-and-white illustration, not bare contour lines.
            mono_progress = min(1.0, max(0.0, t / 0.72))
            mono_reveal = np.clip((mono_progress - mono_order) * 7.0, 0.0, 1.0)
            mono = monochrome.copy()
            mono.putalpha(
                Image.fromarray((monochrome_alpha.astype(np.float32) * mono_reveal).astype(np.uint8))
            )
            canvas.alpha_composite(mono, (x, y))

            # One shared story clock keeps handwriting and colour development together.
            sync_start = 0.42
            # Complete the paired handwriting/colour reveal early, then hold the
            # finished frame long enough to read. Stretching it across the whole
            # scene makes adjacent characters feel disconnected.
            sync_time = min(2.35, max(1.45, duration * 0.48))
            sync_progress = min(1.0, max(0.0, (t - sync_start) / sync_time))
            text_progress = sync_progress
            colour_progress = sync_progress
            colour_reveal = np.clip((colour_progress - colour_order) * 4.2, 0.0, 1.0)
            coloured = colour.copy()
            coloured.putalpha(Image.fromarray((colour_alpha.astype(np.float32) * colour_reveal).astype(np.uint8)))
            canvas.alpha_composite(coloured, (x, y))
            canvas.alpha_composite(self._render_text(text, text_progress))

            # Paper fade instead of conventional scene transitions.
            fade = 1.0
            if t < 0.18:
                fade = t / 0.18
            elif t > duration - 0.28:
                fade = max(0.0, (duration - t) / 0.28)
            if fade < 1.0:
                white = Image.new("RGBA", canvas.size, (*self.paper, 255))
                canvas = Image.blend(white, canvas, fade)
            return np.asarray(canvas.convert("RGB"))

        return VideoClip(make_frame, duration=duration)

    def assemble(self, scenes: Sequence[Dict[str, Any]], keyframes_dir: Path, output: Path) -> Path:
        clips = []
        try:
            for scene in scenes:
                scene_id = int(scene["id"])
                keyframe = self.find_keyframe(keyframes_dir, scene_id)
                clips.append(self.create_scene_clip(scene, keyframe))
                print(f"[OK] minimal_sketch scene {scene_id:02d}: {scene.get('scene_name', '')}")
            final = concatenate_videoclips(clips, method="compose")
            output.parent.mkdir(parents=True, exist_ok=True)
            final.write_videofile(
                str(output), fps=self.fps, codec="libx264", audio=False, preset="medium",
                ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"], logger=None,
            )
            final.close()
        finally:
            for clip in clips:
                clip.close()
        return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate minimal white-paper sketch story video")
    parser.add_argument("--scenes", type=Path, default=ROOT / "output" / "phase1_verified_scenes_with_prompts.json")
    parser.add_argument("--keyframes", type=Path, default=ROOT / "assets" / "keyframes")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "minimal_sketch_demo.mp4")
    parser.add_argument("--fps", type=int, default=12)
    args = parser.parse_args()
    assembler = MinimalSketchVideoAssembler(fps=args.fps)
    scenes = assembler.load_scenes(args.scenes)
    path = assembler.assemble(scenes, args.keyframes, args.output)
    print(f"Minimal sketch video generated: {path}")


if __name__ == "__main__":
    main()
