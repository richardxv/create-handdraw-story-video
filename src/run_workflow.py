"""One-command resumable entry point for the hand-drawn story workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image

from export_keyframe_tasks import export_tasks, find_existing
from export_web_image_kit import export_web_kit
from minimal_sketch_video import MinimalSketchVideoAssembler
from story_parser import StoryParser
from style_prompt_builder import StylePromptBuilder


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
KEYFRAMES = ROOT / "assets" / "keyframes"
SCENES_PATH = OUTPUT / "workflow_scenes.json"
PROMPTS_PATH = OUTPUT / "workflow_scenes_with_prompts.json"
TASKS_PATH = OUTPUT / "keyframe_generation_tasks.json"
STATUS_PATH = OUTPUT / "workflow_status.json"
WEB_IMAGE_DIR = OUTPUT / "image_generation"


def save_status(stage: str, **details: Any) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        json.dumps({"stage": stage, **details}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_story(args: argparse.Namespace) -> str:
    if args.story:
        return args.story.strip()
    if args.story_file:
        return args.story_file.read_text(encoding="utf-8").strip()
    raise ValueError("Provide --story or --story-file when starting a new story.")


def prepare_story(args: argparse.Namespace) -> dict[str, Any]:
    story = read_story(args)
    parser = StoryParser()
    parsed = parser.parse(story, mode="rules")
    parser.save_scenes(parsed, str(SCENES_PATH))

    character_desc = ""
    if args.characters:
        character_desc = args.characters.read_text(encoding="utf-8").strip()
    builder = StylePromptBuilder()
    prompted = builder.build_scene_prompts(parsed, character_desc=character_desc or None)
    builder.save_prompts(prompted, str(PROMPTS_PATH), parsed.get("story_title"))
    data = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    save_status("keyframes_pending", story_title=data.get("story_title"), scene_count=len(prompted))
    return data


def load_prepared_story() -> dict[str, Any]:
    if not PROMPTS_PATH.exists():
        legacy = OUTPUT / "phase1_verified_scenes_with_prompts.json"
        if legacy.exists():
            return json.loads(legacy.read_text(encoding="utf-8"))
        raise FileNotFoundError("No prepared story. Run once with --story or --story-file first.")
    return json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))


def validate_keyframes(scenes: list[dict[str, Any]]) -> tuple[list[int], list[dict[str, Any]]]:
    missing: list[int] = []
    report: list[dict[str, Any]] = []
    for scene in scenes:
        scene_id = int(scene["id"])
        path = find_existing(KEYFRAMES, scene_id)
        if path is None:
            missing.append(scene_id)
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
                valid_ratio = abs(width / height - 0.75) <= 0.08
                report.append({
                    "scene_id": scene_id,
                    "path": str(path),
                    "size": [width, height],
                    "portrait_3_4": valid_ratio,
                })
        except Exception as exc:
            missing.append(scene_id)
            report.append({"scene_id": scene_id, "path": str(path), "error": str(exc)})
    return missing, report


def run(args: argparse.Namespace) -> int:
    data = load_prepared_story() if args.resume else prepare_story(args)
    scenes = data.get("scenes", [])
    missing, keyframe_report = validate_keyframes(scenes)

    if missing:
        web_manifest = export_web_kit(PROMPTS_PATH, WEB_IMAGE_DIR)
        package = export_tasks(PROMPTS_PATH, TASKS_PATH, KEYFRAMES, start_at=min(missing))
        # Keep only genuinely missing scenes; existing later images must not be regenerated.
        package["tasks"] = [task for task in package["tasks"] if task["scene_id"] in missing]
        package["pending_count"] = len(package["tasks"])
        TASKS_PATH.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
        save_status(
            "keyframes_pending",
            story_title=data.get("story_title"),
            missing_scene_ids=missing,
            preferred_generation_mode="web_image_model",
            web_image_workspace=str(WEB_IMAGE_DIR / "prompt_cards.html"),
            recommended_generation_order=web_manifest["generation_order"],
            task_package=str(TASKS_PATH),
            keyframes=keyframe_report,
        )
        print(f"Paused at keyframe generation. Missing scenes: {missing}")
        print(f"Web image workspace (recommended): {WEB_IMAGE_DIR / 'prompt_cards.html'}")
        print(f"Keyframe generation package: {TASKS_PATH}")
        return 2

    output = args.output or OUTPUT / "story_video_latest.mp4"
    save_status("rendering", story_title=data.get("story_title"), keyframes=keyframe_report)
    assembler = MinimalSketchVideoAssembler(fps=args.fps)
    assembler.assemble(scenes, KEYFRAMES, output)
    save_status(
        "complete",
        story_title=data.get("story_title"),
        scene_count=len(scenes),
        keyframes=keyframe_report,
        final_video=str(output),
    )
    print(f"Workflow complete: {output}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or resume the complete hand-drawn story workflow")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--story", help="Plain story text")
    source.add_argument("--story-file", type=Path, help="UTF-8 plain-text story file")
    parser.add_argument("--characters", type=Path, help="Optional reusable character consistency description")
    parser.add_argument("--resume", action="store_true", help="Resume from prepared prompts and keyframes")
    parser.add_argument("--output", type=Path, help="Final MP4 output path")
    parser.add_argument("--fps", type=int, default=12)
    args = parser.parse_args()
    if not args.resume and not (args.story or args.story_file):
        parser.error("a new run requires --story or --story-file; otherwise use --resume")
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
