"""
通用粒子动画层
支持多种粒子类型：雪花、落叶、火星、灰尘、光点等

触发条件：
- "snow" in environment_effects → 雪花
- "falling_leaves" in environment_effects → 落叶
- "fire" in environment_effects → 火星/火花
- "dust" in environment_effects → 灰尘
- "magic" in environment_effects → 魔法光点

也可通过 scene_info["particle_type"] 直接指定类型
"""

import math
import random
from PIL import Image, ImageDraw
from typing import Dict, Any, List
from .base import AnimationLayer


class ParticleLayer(AnimationLayer):
    """通用粒子层"""

    # 预定义粒子类型配置
    PARTICLE_PRESETS = {
        "snow": {
            "count_factor": 80,
            "size_range": (2, 5),
            "speed_range": (30, 70),
            "alpha_range": (120, 200),
            "colors": [(250, 250, 255), (240, 248, 255), (255, 255, 255)],
            "gravity": 0.5,
            "wind_susceptibility": 0.3,
            "shape": "circle"
        },
        "falling_leaves": {
            "count_factor": 25,
            "size_range": (5, 12),
            "speed_range": (40, 90),
            "alpha_range": (100, 180),
            "colors": [(200, 150, 50), (180, 100, 40), (160, 80, 30), (140, 160, 60)],
            "gravity": 0.8,
            "wind_susceptibility": 0.6,
            "shape": "leaf"
        },
        "fire": {
            "count_factor": 40,
            "size_range": (2, 6),
            "speed_range": (60, 150),
            "alpha_range": (150, 255),
            "colors": [(255, 200, 50), (255, 150, 30), (255, 100, 20), (255, 80, 10)],
            "gravity": -0.8,  # 火星向上飘
            "wind_susceptibility": 0.2,
            "shape": "circle"
        },
        "dust": {
            "count_factor": 60,
            "size_range": (1, 3),
            "speed_range": (10, 30),
            "alpha_range": (40, 100),
            "colors": [(200, 190, 170), (180, 175, 160)],
            "gravity": 0.1,
            "wind_susceptibility": 0.1,
            "shape": "circle"
        },
        "magic": {
            "count_factor": 30,
            "size_range": (2, 5),
            "speed_range": (20, 50),
            "alpha_range": (100, 200),
            "colors": [(200, 220, 255), (255, 220, 200), (220, 255, 200)],
            "gravity": -0.3,
            "wind_susceptibility": 0.4,
            "shape": "star"
        }
    }

    def __init__(
        self,
        width: int = 1080,
        height: int = 1440,
        fps: int = 24,
        particle_type: str = "snow",
        intensity: float = 1.0
    ):
        super().__init__(width, height, fps)
        self.particle_type = particle_type
        self.intensity = intensity
        self.preset = self.PARTICLE_PRESETS.get(particle_type, self.PARTICLE_PRESETS["snow"])
        self.particles = self._generate_particles()

    def _generate_particles(self) -> List[Dict[str, Any]]:
        """预生成粒子配置"""
        particles = []
        count = int(self.preset["count_factor"] * self.intensity)

        for _ in range(count):
            particle = {
                "x": random.uniform(0, self.width),
                "y": random.uniform(-self.height, self.height),  # 部分粒子从上方开始
                "size": random.uniform(*self.preset["size_range"]),
                "speed_y": random.uniform(*self.preset["speed_range"]),
                "speed_x": random.uniform(-20, 20),
                "alpha": random.randint(*self.preset["alpha_range"]),
                "color": random.choice(self.preset["colors"]),
                "phase": random.uniform(0, math.pi * 2),
                "oscillation_speed": random.uniform(1, 3),
                "oscillation_amp": random.uniform(10, 30)
            }
            particles.append(particle)
        return particles

    def generate_frame(self, t: float, scene_info: Dict[str, Any]) -> Image.Image:
        """生成带 alpha 的粒子层"""
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        for p in self.particles:
            # 计算粒子位置
            # 垂直移动
            dy = p["speed_y"] * t * self.preset["gravity"]
            # 水平摆动
            dx = p["speed_x"] * t + math.sin(t * p["oscillation_speed"] + p["phase"]) * p["oscillation_amp"]

            x = (p["x"] + dx) % (self.width + 50) - 25
            y = (p["y"] + dy) % (self.height + 100) - 50

            # 根据类型绘制不同形状
            if self.preset["shape"] == "circle":
                self._draw_circle(draw, x, y, p["size"], p["color"], p["alpha"])
            elif self.preset["shape"] == "leaf":
                self._draw_leaf(draw, x, y, p["size"], p["color"], p["alpha"], t)
            elif self.preset["shape"] == "star":
                self._draw_star(draw, x, y, p["size"], p["color"], p["alpha"])

        return img

    def _draw_circle(self, draw: ImageDraw.Draw, x: float, y: float,
                     size: float, color: tuple, alpha: int):
        """绘制圆形粒子"""
        r = size / 2
        color_with_alpha = color + (alpha,)
        draw.ellipse(
            [x - r, y - r, x + r, y + r],
            fill=color_with_alpha
        )

        # 添加高光点（增强立体感）
        if size > 3:
            highlight = tuple(min(255, c + 40) for c in color) + (alpha // 2,)
            draw.ellipse(
                [x - r * 0.3, y - r * 0.3, x + r * 0.1, y + r * 0.1],
                fill=highlight
            )

    def _draw_leaf(self, draw: ImageDraw.Draw, x: float, y: float,
                   size: float, color: tuple, alpha: int, t: float):
        """绘制叶子形状粒子"""
        rotation = t * 90 + math.sin(t * 2) * 30  # 旋转飘落
        rad = math.radians(rotation)

        # 叶子形状（椭圆）
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)

        hx = size * cos_r
        hy = size * sin_r
        wx = size * 0.4 * math.cos(rad + math.pi / 2)
        wy = size * 0.4 * math.sin(rad + math.pi / 2)

        points = [
            (x + hx, y + hy),
            (x + wx, y + wy),
            (x - hx, y - hy),
            (x - wx, y - wy)
        ]

        color_with_alpha = color + (alpha,)
        draw.polygon(points, fill=color_with_alpha)

        # 叶脉
        vein_color = tuple(max(0, c - 30) for c in color) + (alpha // 2,)
        draw.line([(x - hx * 0.5, y - hy * 0.5), (x + hx * 0.5, y + hy * 0.5)],
                  fill=vein_color, width=1)

    def _draw_star(self, draw: ImageDraw.Draw, x: float, y: float,
                   size: float, color: tuple, alpha: int):
        """绘制星形粒子（魔法效果）"""
        num_points = 4
        points = []
        for i in range(num_points * 2):
            angle = math.pi * i / num_points - math.pi / 2
            r = size if i % 2 == 0 else size * 0.4
            px = x + math.cos(angle) * r
            py = y + math.sin(angle) * r
            points.append((px, py))

        color_with_alpha = color + (alpha,)
        draw.polygon(points, fill=color_with_alpha)

        # 中心光点
        glow = tuple(min(255, c + 60) for c in color) + (alpha,)
        draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=glow)
