"""Build style-locked image prompts for every parsed story scene."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class StylePromptBuilder:
    """Combine a fixed art direction, stable characters, and variable scene content."""

    DEFAULT_STYLE_PATH = "prompts/hybrid_style_base.txt"

    def __init__(self, style_base_path: Optional[str] = None):
        self.root = Path(__file__).resolve().parent.parent
        self.style_base_path = Path(style_base_path) if style_base_path else self.root / self.DEFAULT_STYLE_PATH
        if not self.style_base_path.exists():
            raise FileNotFoundError(f"风格模板不存在：{self.style_base_path}")
        self.style_base = self.style_base_path.read_text(encoding="utf-8").strip()

    def build_full_prompt(
        self,
        visual_description: str,
        character_desc: Optional[str] = None,
        extra_rules: Optional[str] = None,
    ) -> str:
        if not isinstance(visual_description, str) or not visual_description.strip():
            raise ValueError("visual_description 不能为空")
        parts = [self.style_base]
        if character_desc and character_desc.strip():
            parts.append("Character consistency rules:\n" + character_desc.strip())
        parts.append("Scene description:\n" + visual_description.strip())
        if extra_rules and extra_rules.strip():
            parts.append("Additional scene rules:\n" + extra_rules.strip())
        parts.append(
            "Output constraints:\n"
            "- Portrait orientation, consistent framing and visual language across the series\n"
            "- Keep a clean area for later subtitle compositing\n"
            "- Camera distance may change, but art style, character proportions, ink-line thickness, cross-hatching density, paper texture, watercolor softness, and detail level must remain identical to the shared reference image\n"
            "- Close-up scenes must not become more realistic, sharper, or more detailed than medium and wide shots\n"
            "- Do not render captions, letters, logos, signatures, or watermarks inside the image"
        )
        return "\n\n".join(parts)

    def build_scene_prompts(
        self,
        scenes_data: Dict[str, Any],
        character_desc: Optional[str] = None,
        extra_rules_per_scene: Optional[Dict[int, str]] = None,
    ) -> List[Dict[str, Any]]:
        if not isinstance(scenes_data, dict) or not isinstance(scenes_data.get("scenes"), list):
            raise ValueError("scenes_data 必须包含 scenes 列表")
        result = []
        for scene in scenes_data["scenes"]:
            if not isinstance(scene, dict):
                continue
            scene_id = scene.get("id", 0)
            copy = dict(scene)
            copy["prompt"] = self.build_full_prompt(
                str(scene.get("visual_description", "")),
                character_desc,
                (extra_rules_per_scene or {}).get(scene_id),
            )
            result.append(copy)
        return result

    def save_prompts(
        self,
        scenes_with_prompts: List[Dict[str, Any]],
        output_path: str,
        story_title: Optional[str] = None,
    ) -> None:
        output = {
            "story_title": story_title or "未命名故事",
            "style_notes": "Hand-drawn children's book illustration style",
            "generation_tips": self.get_consistency_tips_summary(),
            "scenes": scenes_with_prompts,
        }
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[StylePromptBuilder] Prompt 数据已保存：{path}")

    @staticmethod
    def get_consistency_tips_summary() -> Dict[str, Any]:
        return {
            "reference_image_strategy": "优先用角色清楚的中景（通常场景 2 或 6）生成参考图，避免用特写场景锁定风格",
            "seed_strategy": "平台支持时，同批次使用相同或相近 seed",
            "batch_size": "每次生成 2–4 张候选图并筛选风格最一致的一张",
            "prompt_structure": "固定风格 + 固定角色 + 可变场景 + 固定输出约束",
            "negative_prompt_included": True,
            "recommended_resolution": "1080x1440（竖版 3:4）",
            "style_lock_keywords": [
                "loose expressive black ink sketch",
                "cross-hatching shading",
                "generous negative space",
                "warm nostalgic atmosphere",
            ],
        }

    def get_consistency_tips(self) -> str:
        return (
            "1. 先选角色清楚的中景（通常场景 2 或 6）生成参考图，并贯穿整批关键帧。\n"
            "2. 固定风格模板与角色描述，只改变 Scene description。\n"
            "3. 始终使用同一负面提示词、画幅和色彩约束。\n"
            "4. 优先保证线条、交叉阴影、留白和气氛一致。\n"
            "5. 文字由视频合成层添加，不让生图模型绘制文字。"
        )

    def print_prompt_example(self, visual_description: str, character_desc: Optional[str] = None) -> None:
        print(self.build_full_prompt(visual_description, character_desc))


if __name__ == "__main__":
    builder = StylePromptBuilder()
    builder.print_prompt_example("A child finds a wet yellow chick behind a woodpile in a rainy rural courtyard.")
