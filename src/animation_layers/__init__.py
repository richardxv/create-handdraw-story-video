"""
动画层模块

提供故事驱动的动态动画效果层，支持雨、风、粒子、动作线等多种效果。
所有效果层继承自 AnimationLayer 基类，通过 AnimationLayerManager 统一管理。

可用动画层：
- RainLayer: 雨效（倾斜雨滴 + 涟漪）
- WindLayer: 风效（流线 + 飘叶 + 灰尘）
- ParticleLayer: 通用粒子（雪花/落叶/火星/灰尘/魔法光点）
- MotionLinesLayer: 动作线/速度线（speed/radial/impact）
"""

from .base import AnimationLayer
from .manager import AnimationLayerManager
from .rain import RainLayer
from .wind import WindLayer
from .particle import ParticleLayer
from .motion_lines import MotionLinesLayer

__all__ = [
    "AnimationLayer",
    "AnimationLayerManager",
    "RainLayer",
    "WindLayer",
    "ParticleLayer",
    "MotionLinesLayer"
]
