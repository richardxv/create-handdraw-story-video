"""
端到端工作流示例（Phase 3 完整版）

演示从纯故事文本到结构化场景、到生图 Prompt、再到最终视频的完整流程。

完整工作流步骤：
1. Story Parser    → 将故事文本解析为结构化场景
2. Style Prompt Builder → 为每个场景生成完整的 AI 生图 Prompt
3. Image Agent 生图 → 使用生成的 Prompt 批量生成关键帧（手动步骤）
4. Video Assembler → 合成关键帧 + 动画层 + 文字 + 音频 + 质量优化 → 最终 MP4

Phase 3 新增：
- 音频同步（程序化 BGM + 环境音效）
- 多种转场（fade / slide / zoom / wipe）
- 视频质量优化（色彩校正 + 暖色调 + 锐化）

用法：
    python end_to_end_example.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.story_parser import StoryParser
from src.style_prompt_builder import StylePromptBuilder
from src.hybrid_video_assembler_v2 import HybridVideoAssembler


# ========== 示例配置 ==========

STORY_TEXT = """小时候，暑假都住在奶奶家。
奶奶养了一群小鸡，我每天跟着奶奶喂鸡、赶鸡，玩得不亦乐乎。
有一天突然下起大雨，小鸡们四处躲藏，有一只小黄鸡不见了。
我撑着伞在院子里找啊找，最后在柴堆后面发现了它，浑身湿透，瑟瑟发抖。
我把小鸡抱回屋里，奶奶用干毛巾帮它擦干。
雨停后，小鸡又活蹦乱跳了，而我把这段记忆藏在了心里。"""

CHARACTER_DESC = """Character consistency rules (must follow strictly):
- Little boy: round cute face, spiky black hair, big expressive eyes, wearing green long-sleeve shirt and black pants, Q-version proportions, head-to-body ratio around 1:2.5
- Grandma: gray hair tied in a neat bun, blue top, black pants, kind and gentle expression, slightly plump build
- Chickens: simple cute round yellow chick with thin legs; mother hen slightly larger with red comb
- Props: wooden rural gate with latch, tiled roof house, red wooden stool, bamboo winnowing basket, black umbrella, straw pile, puddles on muddy ground"""

OUTPUT_DIR = ROOT / "output"
SCENES_JSON_PATH = OUTPUT_DIR / "scenes.json"
PROMPTS_JSON_PATH = OUTPUT_DIR / "scenes_with_prompts.json"
FINAL_VIDEO_NAME = "my_story_video.mp4"


def step1_parse_story():
    """步骤 1：Story Parser 解析故事"""
    print("\n" + "=" * 60)
    print("步骤 1：Story Parser 解析故事")
    print("=" * 60)

    parser = StoryParser()
    scenes_data = parser.parse(STORY_TEXT, mode="rules")
    parser.print_summary(scenes_data)
    parser.save_scenes(scenes_data, str(SCENES_JSON_PATH))
    return scenes_data


def step2_build_prompts(scenes_data):
    """步骤 2：Style Prompt Builder 生成生图 Prompt"""
    print("\n" + "=" * 60)
    print("步骤 2：Style Prompt Builder 生成生图 Prompt")
    print("=" * 60)

    builder = StylePromptBuilder()
    print("\n【风格一致性技巧】")
    print(builder.get_consistency_tips())

    scenes_with_prompts = builder.build_scene_prompts(scenes_data, character_desc=CHARACTER_DESC)
    builder.save_prompts(scenes_with_prompts, str(PROMPTS_JSON_PATH),
                         story_title=scenes_data.get("story_title", "未命名故事"))

    print(f"\n完整 Prompt 已保存到: {PROMPTS_JSON_PATH}")
    return scenes_with_prompts


def step3_generate_keyframes_manual_note():
    """步骤 3：生成关键帧（手动步骤）"""
    print("\n" + "=" * 60)
    print("步骤 3：使用 Image Agent 生成关键帧（手动步骤）")
    print("=" * 60)
    print("""
请按以下步骤操作：
1. 打开任意 Image Agent 的生图功能
2. 读取 scenes_with_prompts.json 中的 prompt 字段
3. 建议先生成 1 张风格参考图，后续所有图使用相同参考图
4. 设置输出比例为 1080x1440（竖版）
5. 将图片保存到 assets/keyframes/，命名 scene_01.png, scene_02.png, ...
""")


def step4_compose_video(scenes_data):
    """步骤 4：Video Assembler 合成最终视频（Phase 3 完整版）"""
    print("\n" + "=" * 60)
    print("步骤 4：Video Assembler 合成视频（Phase 3 完整版）")
    print("=" * 60)

    assembler = HybridVideoAssembler(
        enable_breathing=True,
        breathing_intensity=0.015,
        text_fadein=0.5,
        text_delay=0.3,
        text_animation_mode="line_by_line",
        transition_type="zoom",
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

    print("\n合成器配置（Phase 3 完整版）：")
    print(f"  呼吸感: {'启用' if assembler.enable_breathing else '关闭'}")
    print(f"  文字动画: {assembler.text_animation_mode}")
    print(f"  转场类型: {assembler.transition_type} ({assembler.transition_duration}s)")
    print(f"  音频: {'启用' if assembler.enable_audio else '关闭'}")
    print(f"  质量优化: {'启用' if assembler.enable_quality else '关闭'}")

    # 打印动画层预览
    print("\n【场景动画层预览】")
    for scene in scenes_data.get("scenes", []):
        layer_names = assembler.layer_manager.get_active_layer_names(scene)
        print(f"  场景 {scene['id']} ({scene['scene_name']}): "
              f"{', '.join(layer_names) if layer_names else '无'}")

    try:
        assembler.assemble(output_name=FINAL_VIDEO_NAME, scenes_data=scenes_data.get("scenes", []))
    except Exception as e:
        print(f"\n视频合成失败: {e}")
        print("请确保关键帧已放入 assets/keyframes/ 目录后再重试。")


def main():
    print("=" * 60)
    print("手绘风格视频生成工作流 - Phase 3 完整版")
    print("=" * 60)
    print(f"\n故事文本:\n{STORY_TEXT}\n")

    scenes_data = step1_parse_story()
    step2_build_prompts(scenes_data)
    step3_generate_keyframes_manual_note()
    step4_compose_video(scenes_data)

    print("\n" + "=" * 60)
    print("工作流执行完毕！")
    print("=" * 60)
    print(f"\n输出文件：")
    print(f"  - 场景数据: {SCENES_JSON_PATH}")
    print(f"  - 生图 Prompt: {PROMPTS_JSON_PATH}")
    print(f"  - 最终视频: {ROOT / 'output' / FINAL_VIDEO_NAME}")


if __name__ == "__main__":
    main()
