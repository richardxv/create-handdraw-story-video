---
name: create-handdraw-story-video
description: "Turn a one- or two-sentence Chinese story idea into a reusable hand-drawn children's picture-book video workflow: expand the story, write a 6-8 scene script, build style-locked image prompts, prepare a browser-friendly Web Image Model workspace or portable image-Agent tasks, review keyframes, and render a warm-paper black-and-white-to-colour MP4. Use when the user asks to make, continue, revise, review, or render a 手绘故事视频、儿童绘本视频、故事动画, or gives a short idea such as 愚公移山 and wants a finished video."
---

# Create Hand-drawn Story Video

Use the containing project as the source of truth. Do not copy its renderer into the Skill.

## Locate the project

Use the current workspace when it contains `WORKFLOW_DESIGN.md` and `src/minimal_sketch_video.py`. Otherwise search accessible workspace roots for both files. If multiple projects match, ask the user which one to use. Never assume a drive letter, username, or absolute path.

Read `WORKFLOW_DESIGN.md` before changing architecture. Read [references/workflow.md](references/workflow.md) before starting or resuming production.

## Execute the workflow

1. Expand a one- or two-sentence idea into a concise Chinese story with a desire, obstacle, action, turn, and emotionally earned ending.
2. Write 6-8 visual scenes, normally 20-30 seconds total. Keep on-screen text short and natural.
3. Create `stories/<story-slug>/`. Never reuse another story's keyframes.
4. Save `story.txt` and `script.json`; build `scenes_with_prompts.json` with `src/style_prompt_builder.py`.
5. Default to Web Image Model mode. Run `src/export_web_image_kit.py` to create the browser prompt workspace and reference prompts.
6. Generate the style reference, character sheet, then scenes in the recommended order. Reuse both references for every scene.
7. Use Image Agent mode only when the system can read files, generate images, and save outputs. Export portable `keyframe_generation_tasks.json` in that mode.
8. Review every keyframe. Reject story mismatches, character drift, style drift, generated text, speech bubbles, logos, signatures, and watermarks.
9. Render with `src/minimal_sketch_video.py`, naming the formal MP4 after the story. Do not call it a demo.
10. Validate MP4 decoding, duration, scene count, text placement, wipe direction, and colour timing.

## Preserve the approved visual behavior

- Warm off-white paper and generous negative space.
- Black-and-white tonal illustration wipes softly from left to right.
- Text and colour then progress together.
- Keep full-line text fixed; fade characters smoothly without shifting prior characters.
- Place text around `y=195` on 1080×1440 unless composition requires adjustment.
- Complete text/colour reveal in about 1.45-2.35 seconds.
- Pace scenes by caption length, normally 3.25-4.05 seconds. The extra 0.5 seconds is reading hold time; do not slow the synchronized text/colour reveal.
- Exclude bottom-edge model marks before tonal conversion.
- Avoid an intermediate high-contrast line-art stage.

## Modify safely

Patch project files with `apply_patch`. Preserve user assets and unrelated edits. Never run overlapping MoviePy jobs against one output. Render to a temporary name when necessary, validate it, then replace the formal output without leaving confusing duplicates.

Run tests after renderer, parser, or exporter changes:

```powershell
python -m unittest discover -s tests -v
```

Use MoviePy's bundled ffmpeg executable for decode checks when `ffmpeg` is unavailable on `PATH`.

## Completion standard

Report complete only when all required keyframes pass review, the formal MP4 exists, decoding returns no errors, and no required work remains. Distinguish one completed story from a finished reusable product.
