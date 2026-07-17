"""Create an offline prompt-card workspace for browser-based image models."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


CLOSEUP_GUARD = """Consistency guard for this scene:
- Camera distance may change, but the art style must not change.
- Preserve exactly the same character proportions, facial design, ink-line thickness, cross-hatching density, paper texture, watercolor softness, and level of detail as the uploaded reference images.
- A close-up must not become more realistic, sharper, or more detailed than medium and wide shots.
- Do not add any text, speech bubbles, letters, logo, signature, or watermark."""


def _extract_character_rules(prompt: str) -> str:
    match = re.search(
        r"Character consistency rules:\s*(.*?)(?:\n\nScene description:|\Z)",
        prompt,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else "Preserve all recurring character designs exactly across the series."


def _reference_scene(scenes: list[dict[str, Any]], requested: int | None) -> dict[str, Any]:
    if requested is not None:
        for scene in scenes:
            if int(scene.get("id", 0)) == requested:
                return scene
        raise ValueError(f"Reference scene {requested} does not exist")
    # Prefer a character-readable medium scene. Avoid close-up/detail scenes by default.
    candidates = [s for s in scenes if int(s.get("id", 0)) in {2, 6}]
    return (candidates or scenes)[0]


def _generation_order(scenes: list[dict[str, Any]]) -> list[int]:
    difficult = re.compile(r"close|detail|hands?|extreme|特写|手部", re.IGNORECASE)
    easy, hard = [], []
    for scene in scenes:
        target = hard if difficult.search(str(scene.get("visual_description", ""))) else easy
        target.append(int(scene["id"]))
    return easy + hard


def _card(scene: dict[str, Any]) -> str:
    scene_id = int(scene["id"])
    prompt = f"{str(scene.get('prompt', '')).strip()}\n\n{CLOSEUP_GUARD}".strip()
    escaped_prompt = html.escape(prompt)
    escaped_name = html.escape(str(scene.get("scene_name", "")))
    escaped_text = html.escape(str(scene.get("on_screen_text", "")))
    filename = f"scene_{scene_id:02d}.png"
    return f"""
    <article class="card" id="scene-{scene_id:02d}">
      <div class="card-head">
        <label><input class="done" type="checkbox" data-id="{scene_id}"> Scene {scene_id:02d} · {escaped_name}</label>
        <code>{filename}</code>
      </div>
      <p class="story">{escaped_text}</p>
      <p class="refs">Upload the same <b>style_reference.png</b> and <b>character_sheet.png</b> for this generation.</p>
      <pre id="prompt-{scene_id:02d}">{escaped_prompt}</pre>
      <button type="button" onclick="copyPrompt('prompt-{scene_id:02d}', this)">Copy prompt</button>
    </article>"""


def _master_instruction(
    data: dict[str, Any],
    scenes: list[dict[str, Any]],
    reference_prompt: str,
    character_prompt: str,
    order: list[int],
) -> str:
    """Create one paste-ready instruction for a web image-model conversation."""
    by_id = {int(scene["id"]): scene for scene in scenes}
    scene_blocks = []
    for scene_id in order:
        scene = by_id[scene_id]
        scene_blocks.append(
            f"## Scene {scene_id:02d} -> scene_{scene_id:02d}.png\n"
            f"Story caption (do not render it in the image): {scene.get('on_screen_text', '')}\n\n"
            f"{str(scene.get('prompt', '')).strip()}\n\n{CLOSEUP_GUARD}"
        )

    return f"""You are the image-production assistant for one complete hand-drawn children's story video.
Complete this whole image set in this same conversation. Do not ask me to repeat individual scene prompts.

Story title: {data.get('story_title', 'Untitled story')}
Theme: {data.get('theme', '')}

Production sequence:
1. First generate one 3:4 portrait master style image named style_reference.png using the prompt below.
2. Then generate one 3:4 portrait character consistency image named character_sheet.png, using the style image you just made as its visual reference.
3. Then generate every scene below in the listed order. Reuse both generated references for every scene and keep character identity, proportions, ink density, paper texture, palette, and detail level fixed across the whole set.

If this website cannot reuse images created earlier in the same conversation, stop after the two reference images and ask me only to upload style_reference.png and character_sheet.png once. After I upload them, continue with every remaining scene without asking for new prompts.

Global requirements:
- Prefer 1080x1440 PNG, 3:4 portrait.
- Create artwork only: never render captions, speech bubbles, letters, signs, logos, signatures, or watermarks.
- Keep generous warm off-white paper space and a restrained hand-drawn picture-book look.
- Generate each numbered scene as a separate image. Preserve the target filename in your response so I can save it correctly.

## style_reference.png
{reference_prompt}

## character_sheet.png
{character_prompt}

## Scene production list

{"\n\n".join(scene_blocks)}
"""


def export_web_kit(source: Path, output_dir: Path, reference_scene_id: int | None = None) -> dict[str, Any]:
    data = json.loads(source.read_text(encoding="utf-8"))
    scenes = data.get("scenes", [])
    if not scenes:
        raise ValueError("Prompt source contains no scenes")
    output_dir.mkdir(parents=True, exist_ok=True)

    reference = _reference_scene(scenes, reference_scene_id)
    reference_prompt = (
        f"{str(reference.get('prompt', '')).strip()}\n\n"
        "Create the master style reference for this entire story series. Use a character-readable medium shot, "
        "balanced negative space, and the exact ink, paper, cross-hatching and watercolor language that every later image must copy. "
        "Do not add text, speech bubbles, letters, logos, signatures, or watermarks."
    )
    character_rules = _extract_character_rules(str(scenes[0].get("prompt", "")))
    character_prompt = (
        f"Create a clean character consistency sheet for this story in the exact style of the uploaded style reference.\n\n"
        f"{character_rules}\n\n"
        "Show each recurring character in front, three-quarter, and side views with consistent face, hair, costume, proportions and props. "
        "Warm off-white paper, ample spacing, no labels, no text, no speech bubbles, no logo, no signature, no watermark."
    )
    (output_dir / "style_reference_prompt.txt").write_text(reference_prompt, encoding="utf-8")
    (output_dir / "character_sheet_prompt.txt").write_text(character_prompt, encoding="utf-8")
    for scene in scenes:
        scene_id = int(scene["id"])
        prompt = f"{str(scene.get('prompt', '')).strip()}\n\n{CLOSEUP_GUARD}"
        (output_dir / f"scene_{scene_id:02d}.txt").write_text(prompt, encoding="utf-8")

    order = _generation_order(scenes)
    master_instruction = _master_instruction(data, scenes, reference_prompt, character_prompt, order)
    (output_dir / "web_model_master_instruction.txt").write_text(master_instruction, encoding="utf-8")
    manifest = {
        "story_title": data.get("story_title", ""),
        "mode": "web_image_model",
        "reference_scene_id": int(reference["id"]),
        "generation_order": ["style_reference", "character_sheet", *[f"scene_{i:02d}" for i in order]],
        "output_directory": "../keyframes",
        "accepted_formats": ["png", "jpg", "jpeg", "webp"],
        "preferred_format": "png",
        "preferred_aspect_ratio": "3:4",
        "preferred_handoff": "web_model_master_instruction.txt",
        "initial_uploads": [],
        "fallback_uploads": ["style_reference.png", "character_sheet.png"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    title = html.escape(str(data.get("story_title", "Hand-drawn Story")))
    cards = "\n".join(_card(scene) for scene in scenes)
    escaped_master_instruction = html.escape(master_instruction)
    order_text = " → ".join(manifest["generation_order"])
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Image Generation Workspace</title>
<style>
:root{{--paper:#f8f4e8;--ink:#27241f;--accent:#a85f36;--card:#fffdf6}}*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}main{{max-width:980px;margin:auto;padding:32px 20px 80px}}
h1{{margin-bottom:4px}}.lead{{margin-top:0;color:#675f53}}.steps,.card{{background:var(--card);border:1px solid #ded5c6;border-radius:16px;padding:20px;margin:18px 0;box-shadow:0 3px 12px #6d5d4512}}
.card-head{{display:flex;justify-content:space-between;gap:12px;align-items:center;font-weight:700}}code{{background:#eee6d8;padding:4px 8px;border-radius:7px}}pre{{white-space:pre-wrap;max-height:360px;overflow:auto;background:#24211d;color:#f9f3e7;padding:16px;border-radius:12px;font:13px/1.55 ui-monospace,monospace}}
button{{border:0;border-radius:9px;padding:10px 15px;background:var(--accent);color:white;font-weight:700;cursor:pointer}}.story{{font-size:18px}}.refs{{color:#675f53}}input{{width:19px;height:19px;vertical-align:-3px}}.done-card{{opacity:.55}}.master pre{{max-height:560px}}
</style></head><body><main>
<h1>{title}</h1><p class="lead">Browser Image Generation Workspace · progress is stored locally in this browser.</p>
<section class="steps"><h2>Preferred one-conversation workflow</h2><ol><li>Open <code>web_model_master_instruction.txt</code> and paste it into the web image model once.</li><li>Let the model create <b>style_reference.png</b>, <b>character_sheet.png</b>, and all scenes in the same conversation.</li><li>Only if the website cannot reuse its own images, upload those two reference images once and tell it to continue.</li><li>Save scene outputs in <code>../keyframes/</code> with the shown filenames. Prefer 3:4 PNG and reject generated text, watermarks, or character/style drift.</li></ol><p><b>Recommended order:</b> {html.escape(order_text)}</p></section>
<section class="steps master"><h2>Master instruction</h2><p>Copy this once and paste it into the web image model.</p><pre id="master-instruction">{escaped_master_instruction}</pre><button type="button" onclick="copyPrompt('master-instruction', this)">Copy master instruction</button></section>
{cards}
</main><script>
const key='web-image-kit:{html.escape(str(data.get('story_title','story')))}';
const state=JSON.parse(localStorage.getItem(key)||'{{}}');
document.querySelectorAll('.done').forEach(x=>{{x.checked=!!state[x.dataset.id];setCard(x);x.addEventListener('change',()=>{{state[x.dataset.id]=x.checked;localStorage.setItem(key,JSON.stringify(state));setCard(x)}})}});
function setCard(x){{x.closest('.card').classList.toggle('done-card',x.checked)}}
async function copyPrompt(id,button){{await navigator.clipboard.writeText(document.getElementById(id).innerText);const old=button.innerText;button.innerText='Copied';setTimeout(()=>button.innerText=old,1000)}}
</script></body></html>"""
    (output_dir / "prompt_cards.html").write_text(page, encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a browser-friendly image generation workspace")
    parser.add_argument("--source", type=Path, required=True, help="scenes_with_prompts.json")
    parser.add_argument("--output", type=Path, help="output directory; defaults to <story>/image_generation")
    parser.add_argument("--reference-scene", type=int, help="scene id for master style reference")
    args = parser.parse_args()
    output = args.output or args.source.parent / "image_generation"
    manifest = export_web_kit(args.source, output, args.reference_scene)
    print(f"Web image workspace: {output / 'prompt_cards.html'}")
    print(f"Reference scene: {manifest['reference_scene_id']}")


if __name__ == "__main__":
    main()
