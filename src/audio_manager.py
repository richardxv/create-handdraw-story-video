"""
音频管理器
负责背景音乐、环境音效、旁白配音的同步和合成

功能：
1. 根据场景生成环境音效（雨声、风声、脚步声等）
2. 支持背景音乐循环
3. 支持旁白配音（TTS 或预录音频）
4. 自动混合所有音频轨道

用法：
    from audio_manager import AudioManager

    audio_mgr = AudioManager()

    # 方式1：程序化生成音效（无需外部文件）
    audio_mgr.add_scene_audio(scenes, scene_durations)

    # 方式2：加载外部音频文件
    audio_mgr.load_background_music("assets/audio/bgm.mp3")
    audio_mgr.load_narration("assets/audio/narration.mp3")

    # 合成最终音频
    final_audio = audio_mgr.mix(final_duration)
"""

import sys
from pathlib import Path
import math
import random
import json

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
from moviepy import AudioClip, CompositeAudioClip, concatenate_audioclips
from typing import Dict, Any, List, Optional, Tuple


def _array_to_audioclip(arr: np.ndarray, fps: int) -> AudioClip:
    """将 numpy 音频数组转换为 AudioClip（避免 AudioArrayClip 单声道 bug）"""
    def frame_function(t):
        if isinstance(t, np.ndarray):
            array_inds = np.round(fps * t).astype(int)
            in_array = (array_inds >= 0) & (array_inds < len(arr))
            n_channels = arr.shape[1] if arr.ndim > 1 else 1
            result = np.zeros((len(t), n_channels))
            if arr.ndim > 1:
                result[in_array] = arr[array_inds[in_array]]
            else:
                result[in_array, 0] = arr[array_inds[in_array]]
            return result
        else:
            i = int(fps * t)
            if i < 0 or i >= len(arr):
                if arr.ndim > 1:
                    return 0 * arr[0]
                else:
                    return np.array([0.0])
            else:
                if arr.ndim > 1:
                    return arr[i]
                else:
                    return np.array([arr[i]])
    duration = 1.0 * len(arr) / fps
    clip = AudioClip(frame_function, duration=duration)
    clip = clip.with_fps(fps)
    clip.nchannels = arr.shape[1] if arr.ndim > 1 else 1
    return clip


# 预定义环境音效生成参数
ENVIRONMENT_SOUND_PRESETS = {
    "rain": {
        "type": "noise",
        "freq_range": (200, 4000),
        "amplitude": 0.06,
        "description": "持续低频雨噪声"
    },
    "wind": {
        "type": "noise",
        "freq_range": (50, 1000),
        "amplitude": 0.04,
        "description": "低频风声呼啸"
    },
    "thunder": {
        "type": "impulse",
        "amplitude": 0.15,
        "duration": 1.0,
        "description": "雷声冲击"
    },
    "footsteps": {
        "type": "rhythmic",
        "amplitude": 0.03,
        "frequency": 2.0,  # 每秒步数
        "description": "脚步声"
    },
    "horse_hooves": {
        "type": "rhythmic",
        "amplitude": 0.05,
        "frequency": 4.0,  # 每秒蹄声数
        "description": "马蹄声"
    },
    "fire": {
        "type": "noise",
        "freq_range": (100, 3000),
        "amplitude": 0.05,
        "description": "火焰噼啪声"
    },
    "birds": {
        "type": "tone",
        "freq_range": (2000, 5000),
        "amplitude": 0.02,
        "description": "鸟鸣"
    },
    "heartbeat": {
        "type": "rhythmic",
        "amplitude": 0.08,
        "frequency": 1.2,  # 每秒心跳
        "description": "心跳声（紧张场景）"
    }
}


class AudioManager:
    """
    音频管理器

    管理三种音频源：
    1. 程序化生成的环境音效（无需外部文件）
    2. 背景音乐（加载外部文件或程序生成）
    3. 旁白配音（TTS 或预录音频）
    """

    # 环境音效 → emotion 映射
    EMOTION_AMBIENT = {
        "warm": "birds",
        "tense": "heartbeat",
        "surprising": "heartbeat",
        "nostalgic": "birds",
        "calm": "birds",
        "dramatic": "thunder",
        "joyful": "birds",
        "sad": "wind"
    }

    def __init__(self, fps: int = 44100):
        """
        初始化音频管理器

        Args:
            fps: 音频采样率（Hz），默认 CD 质量 44100
        """
        self.fps = fps
        self.audio_tracks: List[AudioClip] = []

        # 环境音效配置（按场景组织）
        self.scene_sound_effects: List[Tuple[float, float, Dict[str, Any]]] = []
        # (start_time, duration, effect_config)

    def add_scene_audio(
        self,
        scenes: List[Dict[str, Any]],
        total_duration: float
    ):
        """
        根据场景列表生成环境音效的时间线

        Args:
            scenes: 场景列表（含 environment_effects 和 emotion）
            total_duration: 视频总时长
        """
        current_time = 0.0
        self.scene_sound_effects = []

        for scene in scenes:
            duration = scene.get("duration", 4.5)
            effects = scene.get("environment_effects", ["none"])
            emotion = scene.get("emotion", "calm")

            # 环境效果音效
            for effect in effects:
                if effect in ENVIRONMENT_SOUND_PRESETS:
                    self.scene_sound_effects.append(
                        (current_time, duration, ENVIRONMENT_SOUND_PRESETS[effect])
                    )

            # 情绪辅助音效（如果场景没有特殊环境效果，添加情绪音效）
            if "none" in effects or not effects:
                ambient_key = self.EMOTION_AMBIENT.get(emotion)
                if ambient_key and ambient_key in ENVIRONMENT_SOUND_PRESETS:
                    self.scene_sound_effects.append(
                        (current_time, duration, ENVIRONMENT_SOUND_PRESETS[ambient_key])
                    )

            # 动作音效
            actions = scene.get("key_actions", [])
            for action in actions:
                action_sound = self._action_to_sound(action)
                if action_sound:
                    self.scene_sound_effects.append(
                        (current_time, duration, action_sound)
                    )

            current_time += duration

    def _action_to_sound(self, action: str) -> Optional[Dict[str, Any]]:
        """根据动作关键词推断音效"""
        if any(kw in action for kw in ["跑", "逃", "追", "奔"]):
            return ENVIRONMENT_SOUND_PRESETS["footsteps"]
        if any(kw in action for kw in ["马", "骑"]):
            return ENVIRONMENT_SOUND_PRESETS["horse_hooves"]
        if "摔" in action:
            return {"type": "impulse", "amplitude": 0.1, "duration": 0.3,
                    "description": "摔倒声"}
        return None

    def _generate_noise(
        self,
        duration: float,
        freq_range: Tuple[float, float],
        amplitude: float
    ) -> np.ndarray:
        """
        生成噪声音效（雨声、风声、火焰）

        Args:
            duration: 时长（秒）
            freq_range: 频率范围 (low, high)
            amplitude: 振幅

        Returns:
            numpy 音频数组
        """
        n_samples = int(self.fps * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)

        # 白噪声
        noise = np.random.randn(n_samples)

        # 低通滤波（模拟风声/雨声的频谱特性）
        low_freq = freq_range[0] / self.fps
        high_freq = freq_range[1] / self.fps

        # 简单滑动平均滤波
        window_size = max(1, int(self.fps / freq_range[1] * 10))
        if window_size > 1:
            kernel = np.ones(window_size) / window_size
            noise = np.convolve(noise, kernel, mode='same')

        # 添加振幅调制（模拟自然变化）
        modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 0.3 * t)
        modulation *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.7 * t + 1.0)

        audio = noise * amplitude * modulation

        # 添加淡入淡出
        fade_len = int(self.fps * 0.2)
        audio[:fade_len] *= np.linspace(0, 1, fade_len)
        audio[-fade_len:] *= np.linspace(1, 0, fade_len)

        return audio

    def _generate_impulse(
        self,
        duration: float,
        amplitude: float
    ) -> np.ndarray:
        """
        生成冲击音效（雷声、摔倒声）

        Args:
            duration: 时长（秒）
            amplitude: 振幅

        Returns:
            numpy 音频数组
        """
        n_samples = int(self.fps * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)

        # 指数衰减的冲击波
        envelope = np.exp(-t * 10)
        noise = np.random.randn(n_samples) * envelope * amplitude

        # 添加低频成分（增强冲击感）
        low_freq = 50 / self.fps
        if low_freq > 0:
            low_component = np.sin(2 * np.pi * 50 * t) * envelope * amplitude * 0.5
            noise += low_component

        return noise

    def _generate_rhythmic(
        self,
        duration: float,
        amplitude: float,
        frequency: float
    ) -> np.ndarray:
        """
        生成节奏音效（脚步声、马蹄声、心跳声）

        Args:
            duration: 时长（秒）
            amplitude: 振幅
            frequency: 节奏频率（每秒次数）

        Returns:
            numpy 音频数组
        """
        n_samples = int(self.fps * duration)
        audio = np.zeros(n_samples)

        # 计算节拍位置
        beat_interval = self.fps / frequency
        n_beats = int(duration * frequency)

        for i in range(n_beats):
            start_sample = int(i * beat_interval)
            if start_sample >= n_samples:
                break

            beat_len = min(int(self.fps * 0.08), n_samples - start_sample)
            beat = np.arange(beat_len) / beat_len

            # 冲击 + 衰减的脚步声
            envelope = np.exp(-beat * 20)
            noise = np.random.randn(beat_len) * envelope * amplitude

            # 低频冲击
            low_freq = 100 / self.fps
            low_beat = np.sin(2 * np.pi * 100 * beat * duration) * envelope * amplitude * 0.8

            end = start_sample + beat_len
            audio[start_sample:end] += noise + low_beat

        return audio

    def _generate_ambient_tone(
        self,
        duration: float,
        freq_range: Tuple[float, float],
        amplitude: float
    ) -> np.ndarray:
        """
        生成环境音调（鸟鸣等）

        Args:
            duration: 时长（秒）
            freq_range: 频率范围
            amplitude: 振幅

        Returns:
            numpy 音频数组
        """
        n_samples = int(self.fps * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)

        # 多个正弦波叠加模拟鸟鸣
        audio = np.zeros(n_samples)
        n_tones = random.randint(3, 6)

        for _ in range(n_tones):
            freq = random.uniform(freq_range[0], freq_range[1]) / self.fps
            if freq > 0.5:
                continue
            phase = random.uniform(0, 2 * np.pi)
            tone_amp = amplitude * random.uniform(0.3, 1.0)
            audio += tone_amp * np.sin(2 * np.pi * freq * t + phase)

        # 添加颤音效果
        vibrato = 1.0 + 0.1 * np.sin(2 * np.pi * 5 * t)
        audio *= vibrato

        # 添加间歇性
        silence_mask = (np.sin(2 * np.pi * 0.5 * t) > 0).astype(float)
        audio *= silence_mask * amplitude

        return audio

    def _generate_effect_audio(
        self,
        config: Dict[str, Any],
        duration: float
    ) -> np.ndarray:
        """根据配置生成音效音频"""
        effect_type = config.get("type", "noise")

        if effect_type == "noise":
            return self._generate_noise(
                duration,
                config.get("freq_range", (100, 2000)),
                config.get("amplitude", 0.05)
            )
        elif effect_type == "impulse":
            return self._generate_impulse(
                config.get("duration", 0.5),
                config.get("amplitude", 0.1)
            )
        elif effect_type == "rhythmic":
            return self._generate_rhythmic(
                duration,
                config.get("amplitude", 0.03),
                config.get("frequency", 2.0)
            )
        elif effect_type == "tone":
            return self._generate_ambient_tone(
                duration,
                config.get("freq_range", (1000, 3000)),
                config.get("amplitude", 0.02)
            )
        else:
            return np.zeros(int(self.fps * duration))

    def build_environment_audio(self, total_duration: float) -> Optional[AudioClip]:
        """
        构建所有环境音效的合成音频

        Args:
            total_duration: 音频总时长（秒）

        Returns:
            合成后的音频片段，无音效则返回 None
        """
        if not self.scene_sound_effects:
            return None

        # 创建空音频轨道
        n_samples = int(self.fps * total_duration)
        mixed_audio = np.zeros(n_samples)

        for start_time, duration, effect_config in self.scene_sound_effects:
            if start_time >= total_duration:
                continue

            # 生成该音效的音频
            actual_duration = min(duration, total_duration - start_time)
            effect_audio = self._generate_effect_audio(effect_config, actual_duration)

            # 混入主轨道
            start_sample = int(start_time * self.fps)
            end_sample = start_sample + len(effect_audio)
            if end_sample > n_samples:
                end_sample = n_samples
                effect_audio = effect_audio[:end_sample - start_sample]

            mixed_audio[start_sample:end_sample] += effect_audio

        # 归一化
        max_amp = np.max(np.abs(mixed_audio))
        if max_amp > 0:
            mixed_audio = mixed_audio / max_amp * 0.5

        return _array_to_audioclip(mixed_audio.reshape(-1, 1), fps=self.fps)

    def generate_background_music(
        self,
        duration: float,
        mood: str = "warm",
        amplitude: float = 0.15
    ) -> AudioClip:
        """
        程序化生成背景音乐（无需外部文件）

        根据情绪生成不同调式和节奏的简单旋律。

        Args:
            duration: 音乐时长（秒）
            mood: 情绪（warm, tense, sad, joyful, calm, nostalgic）
            amplitude: 音量

        Returns:
            背景音乐 AudioClip
        """
        n_samples = int(self.fps * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)

        # 根据情绪选择调式和节奏
        mood_config = {
            "warm": {"base_freq": 261.63, "chord_interval": 4, "tempo": 0.5},
            "tense": {"base_freq": 155.56, "chord_interval": 6, "tempo": 0.3},
            "sad": {"base_freq": 196.00, "chord_interval": 5, "tempo": 0.4},
            "joyful": {"base_freq": 329.63, "chord_interval": 3, "tempo": 0.7},
            "calm": {"base_freq": 220.00, "chord_interval": 5, "tempo": 0.35},
            "nostalgic": {"base_freq": 196.00, "chord_interval": 4, "tempo": 0.4},
            "dramatic": {"base_freq": 130.81, "chord_interval": 7, "tempo": 0.25}
        }

        config = mood_config.get(mood, mood_config["warm"])
        base_freq = config["base_freq"] / self.fps
        chord_interval = config["chord_interval"]
        tempo = config["tempo"]

        # 生成和弦进行
        audio = np.zeros(n_samples)

        # 主旋律（琶音）
        for i in range(int(duration / tempo)):
            note_offset = (i % 4) * chord_interval
            freq = base_freq * (2 ** (note_offset / 12))
            if freq > 0.5:
                continue

            note_start = int(i * tempo * self.fps)
            note_duration = int(tempo * 0.8 * self.fps)
            if note_start + note_duration > n_samples:
                note_duration = n_samples - note_start

            if note_duration <= 0:
                continue

            note_t = np.arange(note_duration) / self.fps
            envelope = np.exp(-note_t * 3)  # 衰减

            audio[note_start:note_start + note_duration] += \
                amplitude * np.sin(2 * np.pi * freq * note_t) * envelope

        # 低音持续（增强厚度）
        bass_freq = base_freq * 0.5
        if bass_freq < 0.5:
            bass = amplitude * 0.5 * np.sin(2 * np.pi * bass_freq * t)
            audio += bass

        # 归一化
        max_amp = np.max(np.abs(audio))
        if max_amp > 0:
            audio = audio / max_amp * amplitude

        return _array_to_audioclip(audio.reshape(-1, 1), fps=self.fps)

    def load_external_audio(self, file_path: str, start_time: float = 0.0) -> AudioClip:
        """
        加载外部音频文件（背景音乐、旁白等）

        Args:
            file_path: 音频文件路径
            start_time: 在最终音频中的开始时间（秒）

        Returns:
            加载的 AudioClip
        """
        from moviepy import AudioFileClip

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"音频文件不存在: {path}")

        clip = AudioFileClip(str(path))
        return clip.with_start(start_time)

    def mix(
        self,
        total_duration: float,
        bgm_mood: str = "warm",
        bgm_amplitude: float = 0.12
    ) -> Optional[AudioClip]:
        """
        混合所有音频轨道

        Args:
            total_duration: 最终音频总时长（秒）
            bgm_mood: 背景音乐情绪
            bgm_amplitude: 背景音乐音量

        Returns:
            混合后的最终音频，无任何轨道则返回 None
        """
        clips_to_mix = []

        # 1. 环境音效
        env_audio = self.build_environment_audio(total_duration)
        if env_audio is not None:
            clips_to_mix.append(env_audio)

        # 2. 背景音乐（程序化生成）
        bgm = self.generate_background_music(total_duration, bgm_mood, bgm_amplitude)
        clips_to_mix.append(bgm)

        if not clips_to_mix:
            return None

        if len(clips_to_mix) == 1:
            return clips_to_mix[0]

        # 混合所有轨道
        final_audio = CompositeAudioClip(clips_to_mix)
        final_audio = final_audio.with_duration(total_duration)
        return final_audio

    def get_audio_config_for_story(
        self,
        scenes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        根据故事场景列表，自动生成音频配置

        Returns:
            {
                "bgm_mood": "warm",       # 主情绪
                "bgm_amplitude": 0.12,    # 背景音乐音量
                "total_duration": 45.0,   # 总时长
            }
        """
        if not scenes:
            return {"bgm_mood": "warm", "bgm_amplitude": 0.12, "total_duration": 30.0}

        # 统计情绪
        emotions = [s.get("emotion", "calm") for s in scenes]
        most_common = max(set(emotions), key=emotions.count)

        total_duration = sum(s.get("duration", 4.5) for s in scenes)

        return {
            "bgm_mood": most_common,
            "bgm_amplitude": 0.12,
            "total_duration": total_duration
        }


def demo():
    """
    音频管理器演示

    生成包含环境音效和背景音乐的示例音频。
    """
    print("=" * 60)
    print("AudioManager 演示")
    print("=" * 60)

    audio_mgr = AudioManager()

    # 示例场景
    demo_scenes = [
        {
            "id": 1, "scene_name": "开场", "duration": 4.5,
            "emotion": "nostalgic", "environment_effects": ["none"],
            "key_actions": ["文字出现"]
        },
        {
            "id": 2, "scene_name": "喂鸡日常", "duration": 4.5,
            "emotion": "warm", "environment_effects": ["none"],
            "key_actions": ["奶奶喂鸡", "男孩旁观"]
        },
        {
            "id": 3, "scene_name": "突然下雨", "duration": 4.5,
            "emotion": "tense", "environment_effects": ["rain"],
            "key_actions": ["男孩奔跑", "雨下落"]
        }
    ]

    total_duration = sum(s["duration"] for s in demo_scenes)

    # 添加场景音效
    audio_mgr.add_scene_audio(demo_scenes, total_duration)

    print(f"\n场景数: {len(demo_scenes)}")
    print(f"总时长: {total_duration}s")
    print(f"音效段数: {len(audio_mgr.scene_sound_effects)}")

    # 音效预览
    print("\n【音效时间线】")
    for start_time, duration, config in audio_mgr.scene_sound_effects:
        desc = config.get("description", config.get("type", "unknown"))
        print(f"  {start_time:.1f}s ~ {start_time + duration:.1f}s: {desc}")

    # 混合音频
    print("\n混合音频...")
    audio_config = audio_mgr.get_audio_config_for_story(demo_scenes)
    print(f"  BGM 情绪: {audio_config['bgm_mood']}")

    final_audio = audio_mgr.mix(
        total_duration=total_duration,
        bgm_mood=audio_config["bgm_mood"],
        bgm_amplitude=0.12
    )

    if final_audio is not None:
        print(f"  ✅ 音频合成成功，时长: {final_audio.duration:.1f}s")

        # 保存演示音频
        output_path = ROOT / "output" / "demo_audio.wav"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_audio.write_audiofile(str(output_path), fps=audio_mgr.fps, logger=None)
        print(f"  ✅ 音频已保存: {output_path}")
    else:
        print("  ❌ 音频合成失败")


if __name__ == "__main__":
    demo()