# Workflow reference

## Story package

```text
stories/<story-slug>/
  story.txt
  script.json
  scenes_with_prompts.json
  image_generation/
    prompt_cards.html
    manifest.json
    style_reference_prompt.txt
    character_sheet_prompt.txt
    scene_01.txt ... scene_NN.txt
  keyframe_generation_tasks.json
  keyframes/
    style_reference.png
    character_sheet.png
    scene_01.png ... scene_NN.png
  <story-slug>.mp4
```

Use lowercase ASCII snake_case or hyphen-case for `<story-slug>`.

## Scene schema

Require `id`, `scene_name`, `on_screen_text`, `duration`, `emotion`, `visual_description`, `key_actions`, `environment_effects`, and `notes`. Use one readable visual beat per image and explicitly forbid text inside generated images.

## Web Image Model mode (default)

```powershell
python src\export_web_image_kit.py --source stories\<story-slug>\scenes_with_prompts.json
```

Open `image_generation/prompt_cards.html`. Generate `style_reference.png`, then `character_sheet.png`, then scenes in the manifest order. Upload both references for every scene when supported. Save outputs in `keyframes/` with exact filenames.

Prefer a character-readable medium shot, usually scene 2 or 6, as style reference. Never use a close-up or hands/detail scene as the style anchor. Generate complex close-ups last. Keep proportions, line density, paper texture, watercolour softness, and detail level fixed across camera distances.

## Image Agent mode (optional)

Use `export_tasks()` from `src/export_keyframe_tasks.py` with `portable=True`. Tell the Agent to resolve paths relative to `keyframe_generation_tasks.json`, reuse one reference set, prefer 1080×1440 PNG, save as `scene_01.png` onward, and avoid text, bubbles, logos, signatures, and watermarks.

## Review and render

Check scene count, filenames, dimensions, story match, recurring character design, style language, and generated markings. Regenerate only failed scenes.

```powershell
python src\minimal_sketch_video.py `
  --scenes stories\<story-slug>\script.json `
  --keyframes stories\<story-slug>\keyframes `
  --output stories\<story-slug>\<story-slug>.mp4
```

Approved defaults: 0.72-second monochrome left-to-right wipe; text/colour start near 0.42 seconds; 1.45-2.35-second synchronized reveal; text starts near `y=195`; scenes last 3.25-4.05 seconds, using the added 0.5 seconds as reading hold time; output is 1080×1440 at 12 fps with no audio.
