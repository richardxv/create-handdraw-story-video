"""
动作线/速度线动画层
用于表现快速运动的视觉张力，类似漫画中的速度线效果

触发条件：
- "running" in environment_effects or key_actions
- "horse_running" in environment_effects or key_actions
- "jumping", "falling", "throwing" 等快速动作

效果：
- 集中线（从画面中心向外辐射）
- 速度线（水平或斜向线条）
- 冲击线（强调某个方向的动感）
"""

import math
import random
from PIL import Image, ImageDraw
from typing import Dict, Any, List
from .base import AnimationLayer


class MotionLinesLayer(AnimationLayer):
    """动作线/速度线层"""

    def __init__(
        self,
        width: int = 1080,
        height: int = 1440,
        fps: int = 24,
        line_type: str = "speed",  # "speed" | "impact" | "radial"
        intensity: float = 1.0,
        direction: float = 0.0  # 角度（度），0=水平向右
    ):
        super().__init__(width, height, fps)
        self.line_type = line_type
        self.intensity = intensity
        self.direction = math.radians(direction)

        # 预生成线条配置
        self.lines = self._generate_lines()

    def _generate_lines(self) -> List[Dict[str, Any]]:
        """预生成速度线配置"""
        lines = []

        if self.line_type == "radial":
            # 集中线（从中心向外辐射）
            num_lines = int(30 * self.intensity)
            center_x = self.width // 2
            center_y = self.height // 2
            for _ in range(num_lines):
                angle = random.uniform(0, math.pi * 2)
                lines.append({
                    "center_x": center_x,
                    "center_y": center_y,
                    "angle": angle,
                    "inner_radius": random.randint(50, 150),
                    "outer_radius": random.randint(300, 600),
                    "alpha": random.randint(60, 150),
                    "width": random.randint(1, 3),
                    "speed": random.uniform(2, 5)
                })

        elif self.line_type == "impact":
            # 冲击线（从一侧密集射出）
            num_lines = int(25 * self.intensity)
            origin_x = 0 if self.direction < math.pi / 2 else self.width
            origin_y = random.randint(self.height // 3, self.height * 2 // 3)
            for _ in range(num_lines):
                angle_var = random.uniform(-0.3, 0.3)
                lines.append({
                    "origin_x": origin_x,
                    "origin_y": origin_y + random.randint(-100, 100),
                    "angle": self.direction + angle_var,
                    "length": random.randint(200, 500),
                    "alpha": random.randint(80, 180),
                    "width": random.randint(2, 4),
                    "speed": random.uniform(3, 6)
                })

        else:  # "speed"
            # 速度线（平行线条）
            num_lines = int(40 * self.intensity)
            for _ in range(num_lines):
                lines.append({
                    "x": random.randint(0, self.width),
                    "y": random.randint(0, self.height),
                    "length": random.randint(80, 250),
                    "alpha": random.randint(50, 130),
                    "width": random.randint(1, 3),
                    "speed": random.uniform(100, 250),
                    "phase": random.uniform(0, math.pi * 2)
                })

        return lines

    def generate_frame(self, t: float, scene_info: Dict[str, Any]) -> Image.Image:
        """生成带 alpha 的动作线层"""
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if self.line_type == "radial":
            self._draw_radial_lines(draw, t)
        elif self.line_type == "impact":
            self._draw_impact_lines(draw, t)
        else:
            self._draw_speed_lines(draw, t)

        return img

    def _draw_speed_lines(self, draw: ImageDraw.Draw, t: float):
        """绘制速度线（平行线条，随风/运动方向）"""
        for line in self.lines:
            # 线条位置移动（模拟高速运动）
            speed = line["speed"]
            dx = math.cos(self.direction) * speed * t
            dy = math.sin(self.direction) * speed * t

            x = (line["x"] + dx) % (self.width + 200) - 100
            y = (line["y"] + dy) % (self.height + 100) - 50

            # 添加轻微闪烁效果
            flicker = abs(math.sin(t * 8 + line["phase"]))
            alpha = int(line["alpha"] * (0.5 + 0.5 * flicker))

            # 计算终点
            x2 = x + math.cos(self.direction) * line["length"]
            y2 = y + math.sin(self.direction) * line["length"]

            # 绘制主线条
            draw.line(
                [(x, y), (x2, y2)],
                fill=(30, 30, 30, alpha),
                width=line["width"]
            )

            # 在起点添加小点（运动物体感）
            if flicker > 0.7:
                draw.ellipse(
                    [x - 2, y - 2, x + 2, y + 2],
                    fill=(30, 30, 30, alpha // 2)
                )

    def _draw_radial_lines(self, draw: ImageDraw.Draw, t: float):
        """绘制集中线（从中心向外辐射）"""
        for line in self.lines:
            # 动态效果：线条轻微伸缩
            pulse = 1.0 + 0.1 * math.sin(t * line["speed"])
            inner_r = line["inner_radius"] * pulse
            outer_r = line["outer_radius"] * pulse

            cx, cy = line["center_x"], line["center_y"]
            angle = line["angle"]

            x1 = cx + math.cos(angle) * inner_r
            y1 = cy + math.sin(angle) * inner_r
            x2 = cx + math.cos(angle) * outer_r
            y2 = cy + math.sin(angle) * outer_r

            # 透明度渐变（中心暗，边缘亮）
            alpha = line["alpha"]

            draw.line(
                [(x1, y1), (x2, y2)],
                fill=(40, 40, 40, alpha),
                width=line["width"]
            )

    def _draw_impact_lines(self, draw: ImageDraw.Draw, t: float):
        """绘制冲击线"""
        for line in self.lines:
            # 动态效果：线条从原点快速射出
            progress = min(1.0, t * line["speed"] / 3)
            length = line["length"] * progress

            ox, oy = line["origin_x"], line["origin_y"]
            angle = line["angle"]

            x1 = ox + math.cos(angle) * 20  # 从离原点一点距离开始
            y1 = oy + math.sin(angle) * 20
            x2 = ox + math.cos(angle) * (20 + length)
            y2 = oy + math.sin(angle) * (20 + length)

            # 透明度随时间衰减
            alpha = int(line["alpha"] * (1.0 - progress * 0.3))

            # 绘制粗线（冲击感）
            draw.line(
                [(x1, y1), (x2, y2)],
                fill=(30, 30, 30, alpha),
                width=line["width"]
            )

            # 添加尾迹点
            if progress > 0.5:
                trail_alpha = alpha // 2
                tx = x2 - math.cos(angle) * 15
                ty = y2 - math.sin(angle) * 15
                draw.ellipse(
                    [tx - 2, ty - 2, tx + 2, ty + 2],
                    fill=(30, 30, 30, trail_alpha)
                )
