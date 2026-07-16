"""Export portable pending keyframes for any capable image-generation agent."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "output" / "phase1_verified_scenes_with_prompts.json"
DEFAULT_OUTPUT = ROOT / "output" / "keyframe_generation_tasks.json"


FIXED_RULES = """Execution rules (must follow):
- Generate exactly one vertical 3:4 image for this scene.
- Keep every recurring character, costume, prop, and location consistent with the character rules and shared reference image in this story package.
- Preserve loose black ink lines, cross-hatching, warm off-white paper, muted colors and generous negative space.
- Depict only the requested story beat. Never reuse characters, locations, or props from another story.
- Do not draw subtitles, captions, letters, logos, signatures, or watermarks.
- Preserve generous clean paper space for text added later by the video compositor.
"""


def find_existing(keyframes_dir: Path, scene_id: int) -> Path | None:
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        path = keyframes_dir / f"scene_{scene_id:02d}{suffix}"
        if path.exists():
            return path
    return None


def _portable_path(path: Path, package_dir: Path) -> str:
    return Path(os.path.relpath(path.resolve(), package_dir.resolve())).as_posix()


def export_tasks(
    source: Path, output: Path, keyframes_dir: Path, start_at: int = 1, portable: bool = True
) -> dict:
    data = json.loads(source.read_text(encoding="utf-8"))
    scenes = data.get("scenes", [])
    tasks = []
    completed = []
    for scene in scenes:
        scene_id = int(scene["id"])
        existing = find_existing(keyframes_dir, scene_id)
        if existing and scene_id < start_at:
            completed.append({
                "scene_id": scene_id,
                "path": _portable_path(existing, output.parent) if portable else str(existing.resolve()),
            })
            continue
        if scene_id < start_at:
            continue
        tasks.append({
            "scene_id": scene_id,
            "scene_name": scene.get("scene_name", ""),
            "story_text": scene.get("on_screen_text", ""),
            "target_filename": f"scene_{scene_id:02d}.png",
            "target_directory": (
                _portable_path(keyframes_dir, output.parent) if portable else str(keyframes_dir.resolve())
            ),
            "prompt": f"{scene.get('prompt', '').strip()}\n\n{FIXED_RULES}",
            "acceptance": {
                "story_matches": scene.get("on_screen_text", ""),
                "portrait_3_4": True,
                "contains_written_text": False,
                "uses_old_market_scene": False,
            },
        })
    package = {
        "workflow_stage": "Keyframe Generation",
        "path_mode": "relative_to_task_file" if portable else "absolute",
        "story_title": data.get("story_title", ""),
        "source": _portable_path(source, output.parent) if portable else str(source.resolve()),
        "completed": completed,
        "pending_count": len(tasks),
        "tasks": tasks,
        "next_step": "Save every generated image to target_directory, then return control for validation and MP4 assembly.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return package


def main() -> None:
    parser = argparse.ArgumentParser(description="Export portable pending keyframe tasks for any capable image agent")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--keyframes", type=Path, default=ROOT / "assets" / "keyframes")
    parser.add_argument("--start-at", type=int, default=5)
    args = parser.parse_args()
    package = export_tasks(args.source, args.output, args.keyframes, args.start_at)
    print(f"Keyframe task package: {args.output}")
    print(f"Pending keyframes: {package['pending_count']}")


if __name__ == "__main__":
    main()
