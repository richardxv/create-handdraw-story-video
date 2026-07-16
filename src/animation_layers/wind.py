"""
风效动画层
当 scene_info["environment_effects"] 中包含 "wind" 时启用

效果：
- 风的流线（倾斜线条）
- 飘动的树叶/草叶
- 可选择性开启灰尘/草屑粒子
"""

import math
import random
from PIL import Image, ImageDraw
from typing import Dict, Any, List, Tuple
from .base import AnimationLayer


class WindLayer(AnimationLayer):
    """风效层"""

    def __init__(
        self,
        width: int = 1080,
        height: int = 1440,
        fps: int = 24,
        intensity: float = 1.0,
        wind_direction: float = 30.0  # 风向角度（度），0=从左到右水平
    ):
        super().__init__(width, height, fps)
        self.intensity = intensity  # 风强度系数 0.5~2.0
        self.wind_direction = math.radians(wind_direction)  # 转为弧度

        # 预生成风流线配置（避免每帧随机导致闪烁）
        self.streamlines = self._generate_streamlines()
        self.leaves = self._generate_leaves()

    def _generate_streamlines(self) -> List[Dict[str, Any]]:
        """预生成风流线配置"""
        lines = []
        num_lines = int(15 * self.intensity)
        for _ in range(num_lines):
            lines.append({
                "x": random.randint(0, self.width),
                "y": random.randint(0, self.height),
                "length": random.randint(40, 120),
                "alpha": random.randint(30, 80),
                "speed": random.uniform(80, 150),
                "phase_offset": random.uniform(0, math.pi * 2)
            })
        return lines

    def _generate_leaves(self) -> List[Dict[str, Any]]:
        """预生成飘动树叶配置"""
        leaves = []
        num_leaves = int(8 * self.intensity)
        for _ in range(num_leaves):
            leaves.append({
                "x": random.randint(0, self.width),
                "y": random.randint(0, self.height),
                "size": random.randint(4, 10),
                "speed": random.uniform(60, 120),
                "rotation": random.uniform(0, 360),
                "rot_speed": random.uniform(-90, 90),  # 旋转速度
                "alpha": random.randint(100, 180),
                "color": random.choice([
                    (139, 168, 95, 0),   # 绿叶
                    (180, 160, 100, 0),  # 黄叶
                    (160, 140, 120, 0),  # 枯叶
                ])
            })
        return leaves

    def generate_frame(self, t: float, scene_info: Dict[str, Any]) -> Image.Image:
        """生成带 alpha 的风效层"""
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 1. 绘制风流线
        self._draw_streamlines(draw, t)

        # 2. 绘制飘动树叶
        self._draw_leaves(draw, t)

        # 3. 绘制草屑/灰尘（高强度时）
        if self.intensity >= 1.2:
            self._draw_dust(draw, t)

        return img

    def _draw_streamlines(self, draw: ImageDraw.Draw, t: float):
        """绘制风的流线"""
        for line in self.streamlines:
            # 计算流线的动态位置（随风移动）
            dx = math.cos(self.wind_direction) * line["speed"] * t
            dy = math.sin(self.wind_direction) * line["speed"] * t

            x = int((line["x"] + dx) % (self.width + 200)) - 100
            y = int((line["y"] + dy) % (self.height + 100)) - 50

            # 添加轻微摆动
            wave = math.sin(t * 3 + line["phase_offset"]) * 5

            # 计算终点（考虑风向）
            angle = self.wind_direction + math.radians(wave)
            x2 = int(x + math.cos(angle) * line["length"])
            y2 = int(y + math.sin(angle) * line["length"])

            # 绘制流线（带渐变透明度）
            draw.line(
                [(x, y), (x2, y2)],
                fill=(200, 210, 220, line["alpha"]),
                width=1
            )

            # 在流线末端加小点，增强流动感
            draw.ellipse(
                [x2 - 1, y2 - 1, x2 + 1, y2 + 1],
                fill=(200, 210, 220, line["alpha"] // 2)
            )

    def _draw_leaves(self, draw: ImageDraw.Draw, t: float):
        """绘制飘动的树叶"""
        for leaf in self.leaves:
            # 计算位置（随风移动 + 随机飘动）
            dx = math.cos(self.wind_direction) * leaf["speed"] * t
            dy = math.sin(self.wind_direction) * leaf["speed"] * t * 0.3  # 垂直方向移动较慢

            # 添加随机飘动偏移
            flutter_x = math.sin(t * 2 + leaf["rot_speed"]) * 15
            flutter_y = math.cos(t * 1.5) * 8

            x = int((leaf["x"] + dx + flutter_x) % (self.width + 50)) - 25
            y = int((leaf["y"] + dy + flutter_y) % (self.height + 50)) - 25

            # 计算旋转角度
            rotation = leaf["rotation"] + leaf["rot_speed"] * t
            rad = math.radians(rotation)

            size = leaf["size"]
            # 绘制简单叶子形状（椭圆，带旋转）
            # 用线段模拟叶子
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)

            # 叶子主轴
            hx = size * cos_r
            hy = size * sin_r
            # 叶子副轴
            wx = size * 0.4 * math.cos(rad + math.pi / 2)
            wy = size * 0.4 * math.sin(rad + math.pi / 2)

            # 绘制叶子轮廓
            points = [
                (int(x + hx), int(y + hy)),
                (int(x + wx), int(y + wy)),
                (int(x - hx), int(y - hy)),
                (int(x - wx), int(y - wy))
            ]

            color = leaf["color"][:3] + (leaf["alpha"],)
            draw.polygon(points, fill=color)

    def _draw_dust(self, draw: ImageDraw.Draw, t: float):
        """绘制灰尘/草屑粒子（高强度风时）"""
        num_dust = int(20 * self.intensity)
        for _ in range(num_dust):
            # 快速移动的微小粒子
            speed = random.uniform(150, 250)
            start_x = random.randint(0, self.width)
            start_y = random.randint(0, self.height)

            dx = math.cos(self.wind_direction) * speed * t
            dy = math.sin(self.wind_direction) * speed * t * 0.2

            x = int((start_x + dx) % self.width)
            y = int((start_y + dy) % self.height)

            alpha = random.randint(40, 100)
            size = random.randint(1, 2)

            draw.ellipse(
                [x - size, y - size, x + size, y + size],
                fill=(220, 215, 200, alpha)
            )
