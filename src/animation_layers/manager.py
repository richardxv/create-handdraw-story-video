"""
动画层管理器
根据 scene_info 动态决定需要哪些动画层，并生成合成后的动画层
"""

from typing import List, Dict, Any, Optional
from PIL import Image
import numpy as np

from .base import AnimationLayer
from .rain import RainLayer
from .wind import WindLayer
from .particle import ParticleLayer
from .motion_lines import MotionLinesLayer


class AnimationLayerManager:
    """动画层管理器"""

    def __init__(self, width: int = 1080, height: int = 1440, fps: int = 24):
        self.width = width
        self.height = height
        self.fps = fps

        # 注册所有可用的动画层
        # 注意：这里预实例化，实际使用时根据场景动态选择
        self.available_layers = {
            "rain": RainLayer(width, height, fps, intensity=1.0),
            "wind": WindLayer(width, height, fps, intensity=1.0, wind_direction=30.0),
            "motion_lines": MotionLinesLayer(width, height, fps, line_type="speed", intensity=1.0),
            # 粒子层需要动态创建（因为类型不同参数不同）
        }

    def _get_or_create_particle_layer(self, particle_type: str, intensity: float = 1.0) -> ParticleLayer:
        """根据粒子类型动态创建粒子层"""
        return ParticleLayer(
            self.width, self.height, self.fps,
            particle_type=particle_type,
            intensity=intensity
        )

    def get_active_layers(self, scene_info: Dict[str, Any]) -> List[AnimationLayer]:
        """
        根据场景信息返回当前需要激活的动画层列表

        判断逻辑（按优先级排序）：
        1. environment_effects 直接匹配
        2. key_actions 中间接推断
        3. emotion 辅助判断
        """
        active = []
        effects = scene_info.get("environment_effects", [])
        actions = scene_info.get("key_actions", [])
        emotion = scene_info.get("emotion", "calm")

        # --- 天气效果层 ---

        # 雨效
        if "rain" in effects:
            rain_intensity = 0.55
            # 根据情绪调整强度
            if emotion == "tense":
                rain_intensity = 0.75
            elif emotion == "dramatic":
                rain_intensity = 0.9
            active.append(RainLayer(self.width, self.height, self.fps, intensity=rain_intensity))

        # 风效
        if "wind" in effects:
            wind_intensity = 1.0
            wind_direction = 30.0  # 默认风向
            # 如果有 running 动作，风向与运动方向一致（假设从右向左）
            if any("跑" in a or "逃" in a or "追" in a for a in actions):
                wind_direction = 200.0  # 从右向左
                wind_intensity = 1.3
            active.append(WindLayer(self.width, self.height, self.fps,
                                    intensity=wind_intensity, wind_direction=wind_direction))

        # 雪花
        if "snow" in effects:
            active.append(self._get_or_create_particle_layer("snow", intensity=1.0))

        # 落叶
        if "falling_leaves" in effects:
            active.append(self._get_or_create_particle_layer("falling_leaves", intensity=1.0))

        # 火星/火焰
        if "fire" in effects:
            active.append(self._get_or_create_particle_layer("fire", intensity=1.2))

        # 灰尘
        if "dust" in effects:
            active.append(self._get_or_create_particle_layer("dust", intensity=0.8))

        # 魔法光点
        if "magic" in effects:
            active.append(self._get_or_create_particle_layer("magic", intensity=1.0))

        # --- 动作效果层 ---

        # 速度线（用于快速运动）
        has_fast_action = any(
            keyword in ' '.join(actions)
            for keyword in ["跑", "逃", "追", "跳", "摔", "奔", "冲", "飞"]
        )
        if has_fast_action or "running" in effects or "horse_running" in effects:
            line_type = "speed"
            direction = 0.0
            intensity = 1.0

            # 根据具体动作调整
            if "horse_running" in effects:
                direction = 180.0  # 从右向左
                intensity = 1.3
            elif any("摔" in a or "倒" in a for a in actions):
                line_type = "impact"
                direction = 90.0  # 向下冲击
                intensity = 1.5

            active.append(MotionLinesLayer(self.width, self.height, self.fps,
                                           line_type=line_type, intensity=intensity,
                                           direction=direction))

        # --- 情绪辅助层 ---

        # 紧张/戏剧性场景添加轻微速度线增强氛围
        if emotion in ("tense", "dramatic") and not has_fast_action and "rain" not in effects:
            # 只在已有其他层时添加，避免单独出现过于突兀
            if len(active) > 0:
                active.append(MotionLinesLayer(self.width, self.height, self.fps,
                                               line_type="radial", intensity=0.5))

        return active

    def composite_layers(self, t: float, scene_info: Dict[str, Any]) -> Optional[Image.Image]:
        """
        生成当前时间点所有激活层的合成结果（带 alpha）
        如果没有激活的层，返回 None
        """
        active_layers = self.get_active_layers(scene_info)
        if not active_layers:
            return None

        # 创建透明底图
        base = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))

        for layer in active_layers:
            layer_frame = layer.generate_frame(t, scene_info)
            # 简单叠加（可根据需要改成更复杂的混合模式）
            base = Image.alpha_composite(base, layer_frame)

        return base

    def get_active_layer_names(self, scene_info: Dict[str, Any]) -> List[str]:
        """获取当前场景激活的动画层名称列表（用于调试和日志）"""
        active = self.get_active_layers(scene_info)
        names = []
        for layer in active:
            name = layer.__class__.__name__
            # 如果是粒子层，加上粒子类型
            if isinstance(layer, ParticleLayer):
                name += f"({layer.particle_type})"
            names.append(name)
        return names
