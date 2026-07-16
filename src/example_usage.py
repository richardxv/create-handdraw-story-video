"""
动画层使用示例
"""

from animation_layers.manager import AnimationLayerManager

# 示例场景信息（来自 Story Parser 输出）
scene_info = {
    "id": 4,
    "scene_name": "突然下雨",
    "duration": 4.5,
    "environment_effects": ["rain"],
    "key_actions": ["男孩跑向屋子"],
    "emotion": "tense"
}

manager = AnimationLayerManager()

# 生成第 2 秒的动画层
t = 2.0
layer_image = manager.composite_layers(t, scene_info)

if layer_image:
    layer_image.save("output/rain_layer_test.png")
    print("已生成雨效层测试图：output/rain_layer_test.png")
else:
    print("当前场景无需动画层")
