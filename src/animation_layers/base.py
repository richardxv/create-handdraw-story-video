"""
动画层基类
所有动画效果都应继承此类
"""

from abc import ABC, abstractmethod
from PIL import Image
from typing import Dict, Any
import numpy as np


class AnimationLayer(ABC):
    """动画层抽象基类"""

    def __init__(self, width: int = 1080, height: int = 1440, fps: int = 24):
        self.width = width
        self.height = height
        self.fps = fps

    @abstractmethod
    def generate_frame(self, t: float, scene_info: Dict[str, Any]) -> Image.Image:
        """
        生成单帧动画层（带 alpha 通道）
        t: 当前时间（秒）
        scene_info: 当前场景的完整信息（包含 environment_effects, key_actions 等）
        """
        pass

    def get_duration(self, scene_info: Dict[str, Any]) -> float:
        """返回该动画层的持续时间，默认使用场景时长"""
        return scene_info.get("duration", 4.5)