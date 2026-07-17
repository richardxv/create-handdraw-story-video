import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from story_parser import StoryParser
from style_prompt_builder import StylePromptBuilder
from video_assembler import BasicVideoAssembler
from minimal_sketch_video import MinimalSketchVideoAssembler
from run_workflow import validate_keyframes
from export_web_image_kit import export_web_kit


STORY = (
    "小时候暑假都住在奶奶家。奶奶养了一群小鸡，我每天跟着奶奶喂鸡、赶鸡。"
    "有一天突然下起大雨，小鸡们四处躲藏，一只小黄鸡不见了。"
    "我撑着伞在院子里寻找，最后在柴堆后发现它浑身湿透。"
    "奶奶用干毛巾帮它擦干。雨停后，小鸡又活蹦乱跳，我把这段记忆藏在心里。"
)


class Phase1Tests(unittest.TestCase):
    def test_rule_parser_produces_story_beats(self):
        result = StoryParser().parse(STORY, mode="rules")
        self.assertTrue(StoryParser().validate_scenes(result))
        self.assertGreaterEqual(len(result["scenes"]), 6)
        self.assertLessEqual(len(result["scenes"]), 12)
        self.assertTrue(all(scene["on_screen_text"] for scene in result["scenes"]))

    def test_semantics_and_weather_stop(self):
        scenes = StoryParser().parse(STORY, mode="rules")["scenes"]
        rainy = [s for s in scenes if "大雨" in s["on_screen_text"]][0]
        after_rain = [s for s in scenes if "雨停后" in s["on_screen_text"]][0]
        grandma = [s for s in scenes if "奶奶" in s["on_screen_text"]][0]
        self.assertIn("rain", rainy["environment_effects"])
        self.assertNotIn("rain", after_rain["environment_effects"])
        self.assertIn("grandmother", grandma["visual_description"])

    def test_prompt_builder_preserves_scenes(self):
        parsed = StoryParser().parse(STORY, mode="rules")
        prompts = StylePromptBuilder().build_scene_prompts(parsed, "The child always wears a green shirt.")
        self.assertEqual(len(prompts), len(parsed["scenes"]))
        self.assertTrue(all("prompt" in scene for scene in prompts))
        self.assertTrue(all("Do not render captions" in scene["prompt"] for scene in prompts))

    def test_llm_json_fence_and_save(self):
        parser = StoryParser()
        payload = parser.parse(STORY, mode="rules")
        client = lambda _: "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
        result = parser.parse(STORY, mode="llm", llm_client=client)
        self.assertTrue(parser.validate_scenes(result))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenes.json"
            parser.save_scenes(result, str(path))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["story_title"], result["story_title"])

    def test_basic_video_asset_validation(self):
        assembler = BasicVideoAssembler(width=1080, height=1440, fps=12)
        scenes = [{"id": 1, "duration": 4.5, "on_screen_text": "测试文字"}]
        paths = assembler.validate_assets(scenes, ROOT / "assets" / "keyframes")
        self.assertEqual(paths[0].name, "scene_01.png")
        frame = assembler.render_scene(paths[0], scenes[0]["on_screen_text"])
        self.assertEqual(frame.shape, (1440, 1080, 3))

    def test_minimal_sketch_line_art_and_text(self):
        assembler = MinimalSketchVideoAssembler(width=1080, height=1440, fps=12)
        ink, order = assembler._make_line_art(ROOT / "assets" / "keyframes" / "scene_01.png")
        self.assertEqual(ink.mode, "RGBA")
        self.assertEqual(order.shape, (ink.height, ink.width))
        self.assertGreater(ink.getchannel("A").getbbox()[2], 0)
        self.assertLessEqual(len(assembler._wrap_text("这是一段用于测试自动换行的较长故事文字")), 3)


    def test_resumable_workflow_validates_keyframes(self):
        missing, report = validate_keyframes([{"id": 1}, {"id": 2}])
        self.assertEqual(missing, [])
        self.assertEqual([item["scene_id"] for item in report], [1, 2])
        self.assertTrue(all("portrait_3_4" in item for item in report))

    def test_web_image_kit_is_portable_and_complete(self):
        source = ROOT / "output" / "phase1_verified_scenes_with_prompts.json"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "image_generation"
            manifest = export_web_kit(source, output)
            self.assertTrue((output / "prompt_cards.html").exists())
            self.assertTrue((output / "web_model_master_instruction.txt").exists())
            master_instruction = (output / "web_model_master_instruction.txt").read_text(encoding="utf-8")
            self.assertIn("style_reference.png", master_instruction)
            self.assertIn("character_sheet.png", master_instruction)
            self.assertIn("scene_01.png", master_instruction)
            self.assertIn("Do not ask me questions", master_instruction)
            self.assertIn("Never stop for user confirmation", master_instruction)
            workspace = (output / "prompt_cards.html").read_text(encoding="utf-8")
            self.assertIn('id="master-instruction"', workspace)
            self.assertIn("Copy master instruction", workspace)
            self.assertTrue((output / "style_reference_prompt.txt").exists())
            self.assertTrue((output / "character_sheet_prompt.txt").exists())
            self.assertEqual(len(list(output.glob("scene_*.txt"))), len(json.loads(source.read_text(encoding="utf-8"))["scenes"]))
            self.assertEqual(manifest["output_directory"], "../keyframes")
            self.assertTrue(manifest["keyframe_directory_display"].replace("\\", "/").endswith("keyframes"))
            self.assertEqual(manifest["mode"], "web_image_model")
            self.assertEqual(manifest["preferred_handoff"], "web_model_master_instruction.txt")


if __name__ == "__main__":
    unittest.main()
