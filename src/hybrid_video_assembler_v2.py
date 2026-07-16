"""
混合方案视频合成器 v3（Phase 3 完整版）
整合：
- Image Agent 生成的关键帧
- 故事驱动的动画层（AnimationLayerManager）
- 文字叠加（逐行或整体淡入）
- 关键帧呼吸感（Ken Burns 效果）
- 场景间转场（fade / slide / zoom / wipe）
- 视频质量优化（色彩校正 + 锐化）
- 音频同步（程序化 BGM + 环境音效）
- 多场景视频合成
"""

import sys
from pathlib import Path

# 将项目根目录加入 sys.path，确保能正确导入 src 包
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import math
from moviepy import VideoClip, CompositeVideoClip, concatenate_videoclips
from moviepy.video.fx.FadeIn import FadeIn
from moviepy.video.fx.FadeOut import FadeOut
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import json
import random
from typing import Dict, Any, List, Optional

from src.animation_layers.manager import AnimationLayerManager
from src.audio_manager import AudioManager
from src.transitions import apply_transition
from src.video_quality import process_frame, StabilizeFilter

KEYFRAMES_DIR = ROOT / "assets" / "keyframes"
SCENES_PATH = ROOT / "prompts" / "scenes_prompts.json"


class HybridVideoAssembler:
    """
    混合视频合成器 v3

    将关键帧、动画层、文字叠加、音频、质量优化合成为最终视频。
    支持呼吸感、文字动画、多种转场、色彩校正、程序化音频。
    """

    def __init__(
        self,
        width: int = 1080,
        height: int = 1440,
        fps: int = 24,
        enable_breathing: bool = True,
        breathing_intensity: float = 0.015,
        text_fadein: float = 0.5,
        text_delay: float = 0.3,
        text_animation_mode: str = "line_by_line",  # "all" | "line_by_line"
        transition_type: str = "fade",  # "fade" | "slide" | "zoom" | "wipe" | "none"
        transition_duration: float = 0.6,
        enable_audio: bool = True,
        bgm_amplitude: float = 0.12,
        enable_quality: bool = True,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        warmth: float = 1.15,
        sharpness: float = 0.5,
        enable_stabilization: bool = False,
        keyframes_subdir: str = ""  # 关键帧子文件夹名，如 "mengmu"
    ):
        """
        初始化合成器

        Args:
            width: 视频宽度
            height: 视频高度
            fps: 帧率
            enable_breathing: 是否启用关键帧呼吸感
            breathing_intensity: 呼吸感强度（0.01 = 1% 缩放）
            text_fadein: 文字淡入持续时间（秒）
            text_delay: 文字出现前的延迟（秒）
            text_animation_mode: "all"=全部一起淡入, "line_by_line"=逐行依次出现
            transition_type: 转场类型 "fade"/"slide"/"zoom"/"wipe"/"none"
            transition_duration: 场景间转场持续时间（秒）
            enable_audio: 是否启用音频（程序化 BGM + 环境音效）
            bgm_amplitude: 背景音乐音量
            enable_quality: 是否启用视频质量优化
            brightness: 亮度
            contrast: 对比度
            saturation: 饱和度
            warmth: 暖色调（>1.0 偏暖，<1.0 偏冷）
            sharpness: 锐化强度（0=无，推荐0.3~1.0）
            enable_stabilization: 是否启用帧间稳定（实验性）
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.enable_breathing = enable_breathing
        self.breathing_intensity = breathing_intensity
        self.text_fadein = text_fadein
        self.text_delay = text_delay
        self.text_animation_mode = text_animation_mode
        self.transition_type = transition_type
        self.transition_duration = transition_duration
        self.enable_audio = enable_audio
        self.bgm_amplitude = bgm_amplitude
        self.enable_quality = enable_quality
        self.quality_config = {
            "brightness": brightness,
            "contrast": contrast,
            "saturation": saturation,
            "warmth": warmth,
            "sharpness": sharpness
        }
        self.enable_stabilization = enable_stabilization
        self.keyframes_dir = KEYFRAMES_DIR / keyframes_subdir if keyframes_subdir else KEYFRAMES_DIR

        self.layer_manager = AnimationLayerManager(width, height, fps)
        self.audio_manager = AudioManager() if enable_audio else None
        self.stabilize_filter = StabilizeFilter(window_size=3) if enable_stabilization else None

    def load_scenes(self, scenes_path: Path = None) -> List[Dict]:
        """加载场景数据（可来自 Story Parser 输出）"""
        path = scenes_path or SCENES_PATH
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 支持两种格式：直接是列表，或包含 scenes 字段的字典
            if isinstance(data, list):
                return data
            return data.get("scenes", [])

    def _load_font(self, font_size: int = 42):
        """加载字体，失败则返回默认字体"""
        try:
            return ImageFont.truetype(str(ROOT / "assets" / "fonts" / "handwrite.ttf"), font_size)
        except Exception:
            try:
                # 尝试加载常见中文字体
                return ImageFont.truetype("msyh.ttc", font_size)
            except Exception:
                return ImageFont.load_default()

    def _split_text_lines(self, text: str) -> List[str]:
        """将字幕均衡分成最多两行，避免遮挡画面主体。"""
        clean = ''.join(text.replace('\n', '，').split())
        if not clean:
            return []
        if len(clean) <= 20:
            return [clean]
        midpoint = len(clean) // 2
        candidates = [i for i, char in enumerate(clean) if char in '，。！？；']
        split_at = min(candidates, key=lambda i: abs(i - midpoint)) + 1 if candidates else midpoint
        return [clean[:split_at], clean[split_at:]]

    def _prepare_base_image(self, image: Image.Image) -> Image.Image:
        """适配竖版画布：模糊铺底并完整保留原图，杜绝黑边。"""
        image = image.convert('RGBA')
        cover_scale = max(self.width / image.width, self.height / image.height)
        cover_size = (round(image.width * cover_scale), round(image.height * cover_scale))
        cover = image.resize(cover_size, Image.Resampling.LANCZOS)
        left = (cover.width - self.width) // 2
        top = (cover.height - self.height) // 2
        background = cover.crop((left, top, left + self.width, top + self.height))
        background = background.filter(ImageFilter.GaussianBlur(radius=28))

        contain_scale = min(self.width / image.width, self.height / image.height)
        contain_size = (round(image.width * contain_scale), round(image.height * contain_scale))
        foreground = image.resize(contain_size, Image.Resampling.LANCZOS)
        x = (self.width - foreground.width) // 2
        y = (self.height - foreground.height) // 2
        background.alpha_composite(foreground, (x, y))
        return background

    def render_text_layer(self, text: str, font_size: int = 42) -> Image.Image:
        """
        渲染完整文字层（透明背景，RGBA）

        将所有文字渲染为一张透明图层（用于 "all" 模式）。
        """
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = self._load_font(font_size)

        lines = self._split_text_lines(text)
        if not lines:
            return img

        line_height = font_size + 12
        panel_height = 244
        panel_top = self.height - panel_height - 42
        draw.rounded_rectangle(
            (62, panel_top, self.width - 62, self.height - 42),
            radius=24, fill=(255, 252, 244, 238), outline=(70, 60, 50, 55), width=2
        )
        text_block_height = len(lines) * line_height
        y = panel_top + (panel_height - text_block_height) // 2

        for line in lines:
            x_off = random.randint(-2, 2)
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = max(82, (self.width - text_w) // 2 + x_off)

            draw.text((x + 1, y + 1), line, font=font, fill=(0, 0, 0, 60))
            draw.text((x, y), line, font=font, fill=(30, 30, 30, 230))
            y += line_height

        return img

    def render_text_lines(self, text: str, font_size: int = 42) -> List[Image.Image]:
        """
        将每行文字分别渲染为独立的透明图层（用于 "line_by_line" 模式）

        返回与行数相同的图层列表，每行在其正确的位置上。
        """
        lines = self._split_text_lines(text)
        if not lines:
            return []

        font = self._load_font(font_size)
        line_height = font_size + 12
        panel_height = 244
        panel_top = self.height - panel_height - 42
        text_block_height = len(lines) * line_height
        base_y = panel_top + (panel_height - text_block_height) // 2

        result = []
        for i, line in enumerate(lines):
            img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            draw.rounded_rectangle(
                (62, panel_top, self.width - 62, self.height - 42),
                radius=24, fill=(255, 252, 244, 238), outline=(70, 60, 50, 55), width=2
            )

            x_off = random.randint(-2, 2)
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = max(82, (self.width - text_w) // 2 + x_off)
            y = base_y + i * line_height

            draw.text((x + 1, y + 1), line, font=font, fill=(0, 0, 0, 60))
            draw.text((x, y), line, font=font, fill=(30, 30, 30, 230))

            result.append(img)

        return result

    def _calculate_text_alpha(self, t: float, line_index: int = 0, total_lines: int = 1) -> float:
        """
        计算文字在当前时间的透明度

        支持两种模式：
        - "all": 所有行一起淡入
        - "line_by_line": 每行依次出现，间隔 0.3s
        """
        if self.text_animation_mode == "line_by_line" and total_lines > 1:
            # 逐行模式：每行延迟 0.3s
            line_delay = self.text_delay + line_index * 0.3
            fade_start = line_delay
            fade_end = line_delay + self.text_fadein
        else:
            fade_start = self.text_delay
            fade_end = self.text_delay + self.text_fadein

        if t < fade_start:
            return 0.0
        elif t > fade_end:
            return 1.0
        else:
            return (t - fade_start) / self.text_fadein

    def _apply_quality(self, frame: np.ndarray) -> np.ndarray:
        """对帧应用视频质量优化（色彩校正 + 锐化）"""
        if not self.enable_quality:
            return frame
        return process_frame(frame, self.quality_config)

    def _apply_breathing(self, img: Image.Image, t: float, duration: float) -> Image.Image:
        """
        应用呼吸感（Ken Burns 效果）

        通过轻微的正弦波缩放和位移，让静态关键帧产生微妙的生命力。
        缩放周期等于场景时长，确保每个场景从正常大小开始和结束。

        Args:
            img: 原始关键帧
            t: 当前时间（秒）
            duration: 场景总时长（秒）

        Returns:
            处理后的图像
        """
        if not self.enable_breathing or duration <= 0:
            return img

        # 正弦波相位：从 0 开始，到 2π 结束
        phase = 2 * math.pi * t / duration

        # 缩放：1.0 ± intensity
        scale = 1.0 + self.breathing_intensity * math.sin(phase)

        # 位移：轻微漂移，与缩放相位错开 π/2
        drift_x = self.breathing_intensity * 30 * math.cos(phase)
        drift_y = self.breathing_intensity * 20 * math.sin(phase + math.pi / 4)

        # 计算新尺寸
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))

        # 使用高质量重采样
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 计算裁剪区域（居中 + 漂移）
        left = (new_w - self.width) // 2 + int(drift_x)
        top = (new_h - self.height) // 2 + int(drift_y)

        # 边界检查
        left = max(0, min(left, new_w - self.width))
        top = max(0, min(top, new_h - self.height))

        return resized.crop((left, top, left + self.width, top + self.height))

    def create_scene_clip(self, scene: Dict[str, Any], duration: float):
        """
        创建单个场景的视频片段

        合成流程：
        1. 加载关键帧
        2. 应用呼吸感（Ken Burns）
        3. 叠加动画层（雨/风/粒子/动作线等）
        4. 叠加文字层（支持逐行出现或整体淡入）
        """
        scene_id = scene["id"]
        # 兼容 .png 和 .jpg 格式（GenerateImage 可能输出 .jpg）
        keyframe_path = self.keyframes_dir / f"scene_{scene_id:02d}.png"
        if not keyframe_path.exists():
            keyframe_path = self.keyframes_dir / f"scene_{scene_id:02d}.jpg"

        if not keyframe_path.exists():
            raise FileNotFoundError(f"关键帧不存在: {keyframe_path}")

        # 加载关键帧
        with Image.open(keyframe_path) as source:
            base_img = self._prepare_base_image(source)

        # 预渲染文字层（根据动画模式选择）
        text = scene.get("on_screen_text", "")
        text_layer_all = None      # 完整文字层（"all" 模式）
        text_layers_lines = []     # 逐行文字层（"line_by_line" 模式）

        if text:
            if self.text_animation_mode == "line_by_line":
                text_layers_lines = self.render_text_lines(text)
            else:
                text_layer_all = self.render_text_layer(text)

        def make_frame(t):
            # 1. 应用呼吸感
            frame = self._apply_breathing(base_img, t, duration)

            # 2. 获取动画层
            layer_img = self.layer_manager.composite_layers(t, scene)

            # 3. 合成关键帧 + 动画层
            if layer_img:
                frame = Image.alpha_composite(frame, layer_img)

            # 4. 合成文字层
            if text_layer_all is not None:
                # 模式：全部一起淡入
                alpha = self._calculate_text_alpha(t)
                if alpha > 0:
                    if alpha < 1.0:
                        text_copy = text_layer_all.copy()
                        r, g, b, a = text_copy.split()
                        a = a.point(lambda x: int(x * alpha))
                        text_copy = Image.merge('RGBA', (r, g, b, a))
                        frame = Image.alpha_composite(frame, text_copy)
                    else:
                        frame = Image.alpha_composite(frame, text_layer_all)

            elif text_layers_lines:
                # 模式：逐行依次出现
                total_lines = len(text_layers_lines)
                for idx, line_layer in enumerate(text_layers_lines):
                    alpha = self._calculate_text_alpha(t, line_index=idx, total_lines=total_lines)
                    if alpha > 0:
                        if alpha < 1.0:
                            line_copy = line_layer.copy()
                            r, g, b, a = line_copy.split()
                            a = a.point(lambda x: int(x * alpha))
                            line_copy = Image.merge('RGBA', (r, g, b, a))
                            frame = Image.alpha_composite(frame, line_copy)
                        else:
                            frame = Image.alpha_composite(frame, line_layer)

            # 5. 应用视频质量优化
            rgb_frame = np.array(frame.convert("RGB"))
            return self._apply_quality(rgb_frame)

        clip = VideoClip(make_frame, duration=duration)
        return clip

    def assemble(
        self,
        scenes_path: Path = None,
        output_name: str = "final_video.mp4",
        scenes_data: Optional[List[Dict]] = None
    ):
        """
        组装完整视频

        Args:
            scenes_path: 场景 JSON 文件路径
            output_name: 输出视频文件名
            scenes_data: 直接传入场景数据（优先级高于 scenes_path）
        """
        if scenes_data is not None:
            scenes = scenes_data
        else:
            scenes = self.load_scenes(scenes_path)

        clips = []
        print("开始合成视频...")

        for scene in scenes:
            duration = scene.get("duration", 4.5)
            try:
                clip = self.create_scene_clip(scene, duration)
                clips.append(clip)
                print(f"  [OK] 场景 {scene['id']}: {scene.get('scene_name', '')} ({duration}s)")
            except Exception as e:
                print(f"  [FAIL] 场景 {scene['id']} 失败: {e}")

        if not clips:
            print("没有可用的场景，合成终止。")
            return

        # 应用场景间转场（使用 CompositeVideoClip 重叠时间线 + FadeIn/FadeOut）
        if self.transition_type != "none" and self.transition_duration > 0 and len(clips) > 1:
            print(f"应用转场效果（{self.transition_type} {self.transition_duration}s）...")
            composite_clips = []
            current_time = 0.0
            for i, clip in enumerate(clips):
                clip_copy = clip.copy()
                # 第一个场景只在末尾 fade out，中间场景两头都有，最后一个只在开头 fade in
                effects = []
                if i > 0:
                    effects.append(FadeIn(self.transition_duration))
                if i < len(clips) - 1:
                    effects.append(FadeOut(self.transition_duration))
                if effects:
                    clip_copy = clip_copy.with_effects(effects)
                clip_copy = clip_copy.with_start(current_time)
                composite_clips.append(clip_copy)
                current_time += clip.duration - self.transition_duration
            final_video = CompositeVideoClip(composite_clips)
        else:
            # 无转场：直接拼接
            final_video = concatenate_videoclips(clips, method="compose")

        # 添加音频
        if self.enable_audio and self.audio_manager is not None:
            print("添加音频（背景音乐 + 环境音效）...")
            total_duration = final_video.duration
            self.audio_manager.add_scene_audio(scenes, total_duration)
            audio_config = self.audio_manager.get_audio_config_for_story(scenes)
            final_audio = self.audio_manager.mix(
                total_duration=total_duration,
                bgm_mood=audio_config["bgm_mood"],
                bgm_amplitude=self.bgm_amplitude
            )
            if final_audio is not None:
                final_video = final_video.with_audio(final_audio)
                print(f"  [OK] 音频已合成（BGM: {audio_config['bgm_mood']}, {total_duration:.1f}s）")

        output_path = ROOT / "output" / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)

        final_video.write_videofile(
            str(output_path),
            fps=self.fps,
            codec="libx264",
            audio=self.enable_audio,
            logger=None
        )
        print(f"\n[OK] 视频已生成: {output_path}")


def demo():
    """
    视频合成器演示（Phase 3 完整版）

    使用示例场景数据测试合成流程（无需真实关键帧）。
    如果关键帧不存在，会显示错误提示。
    """
    print("=" * 60)
    print("Hybrid Video Assembler v3 - 演示")
    print("=" * 60)

    # 创建合成器（启用所有 Phase 3 增强效果）
    assembler = HybridVideoAssembler(
        enable_breathing=True,
        breathing_intensity=0.02,
        text_fadein=0.5,
        text_delay=0.3,
        text_animation_mode="line_by_line",
        transition_type="zoom",  # 使用 zoom 转场
        transition_duration=0.8,
        enable_audio=True,
        bgm_amplitude=0.12,
        enable_quality=True,
        brightness=1.05,
        contrast=1.0,
        saturation=1.0,
        warmth=1.15,
        sharpness=0.5,
        enable_stabilization=False
    )

    # 示例场景数据（含多种环境效果，测试音频）
    demo_scenes = [
        {
            "id": 1,
            "scene_name": "开场",
            "duration": 4.5,
            "emotion": "nostalgic",
            "on_screen_text": "小时候，暑假都住在奶奶家",
            "environment_effects": ["none"],
            "key_actions": ["文字出现"]
        },
        {
            "id": 2,
            "scene_name": "喂鸡日常",
            "duration": 4.5,
            "emotion": "warm",
            "on_screen_text": "",
            "environment_effects": ["none"],
            "key_actions": ["奶奶喂鸡", "男孩旁观"]
        },
        {
            "id": 3,
            "scene_name": "突然下雨",
            "duration": 5.0,
            "emotion": "tense",
            "on_screen_text": "不好了，小鸡不见了",
            "environment_effects": ["rain"],
            "key_actions": ["男孩奔跑", "雨下落"]
        },
        {
            "id": 4,
            "scene_name": "找到小鸡",
            "duration": 5.0,
            "emotion": "warm",
            "on_screen_text": "在柴堆后面找到了它",
            "environment_effects": ["none"],
            "key_actions": ["男孩蹲下", "抱起小鸡"]
        },
        {
            "id": 5,
            "scene_name": "温馨结尾",
            "duration": 5.0,
            "emotion": "nostalgic",
            "on_screen_text": "这段记忆藏在了心里",
            "environment_effects": ["none"],
            "key_actions": ["奶奶擦干小鸡", "男孩微笑"]
        }
    ]

    print("\n演示配置（Phase 3 完整版）：")
    print(f"  呼吸感: {'启用' if assembler.enable_breathing else '关闭'} (强度 {assembler.breathing_intensity})")
    print(f"  文字动画: {assembler.text_animation_mode} (淡入 {assembler.text_fadein}s)")
    print(f"  转场类型: {assembler.transition_type} ({assembler.transition_duration}s)")
    print(f"  音频: {'启用' if assembler.enable_audio else '关闭'} (BGM音量 {assembler.bgm_amplitude})")
    print(f"  质量优化: {'启用' if assembler.enable_quality else '关闭'}")
    print(f"    暖色调: {assembler.quality_config['warmth']}, 锐化: {assembler.quality_config['sharpness']}")
    print(f"  场景数: {len(demo_scenes)}")

    # 预览动画层
    print("\n【场景动画层预览】")
    for scene in demo_scenes:
        layer_names = assembler.layer_manager.get_active_layer_names(scene)
        print(f"  场景 {scene['id']} ({scene['scene_name']}): {', '.join(layer_names) if layer_names else '无'}")

    print("\n注意：此演示需要 assets/keyframes/scene_01.png ~ scene_05.png 存在。")
    print("如果关键帧不存在，请先生成关键帧后再运行。\n")

    # 尝试合成（需要真实关键帧才能成功）
    try:
        assembler.assemble(output_name="demo_video_v3.mp4", scenes_data=demo_scenes)
    except Exception as e:
        print(f"演示失败（预期行为，如果关键帧不存在）: {e}")
        print("\n提示：请将 Image Agent 生成的关键帧放入 assets/keyframes/ 目录")
        print("      文件命名格式: scene_01.png, scene_02.png, ...")


if __name__ == "__main__":
    demo()
