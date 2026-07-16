"""
雨效动画层（故事驱动示例）
当 scene_info["environment_effects"] 中包含 "rain" 时启用
"""

import random
import numpy as np
from PIL import Image, ImageDraw
from typing import Dict, Any
from .base import AnimationLayer


class RainLayer(AnimationLayer):
    """雨效层"""

    def __init__(self, width: int = 1080, height: int = 1440, fps: int = 24,
                 intensity: float = 1.0):
        super().__init__(width, height, fps)
        self.intensity = intensity  # 雨的强度系数

    def generate_frame(self, t: float, scene_info: Dict[str, Any]) -> Image.Image:
        """生成带 alpha 的雨层"""
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 根据时间和强度计算雨滴数量
        base_drops = int(100 * self.intensity)
        num_drops = int(base_drops + random.randint(-10, 10))

        for _ in range(num_drops):
            # 随机位置 + 时间偏移模拟下落
            x = random.randint(0, self.width)
            y = int((random.random() * self.height + t * 180) % (self.height + 100)) - 50

            length = random.randint(12, 26)
            alpha = random.randint(60, 150)

            # 轻微斜雨
            x2 = x + random.randint(4, 8)
            y2 = y + length

            draw.line([(x, y), (x2, y2)], fill=(170, 190, 215, alpha), width=1)

        return img
