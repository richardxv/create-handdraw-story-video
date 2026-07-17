# Hand-drawn Story Video Workflow

Turn a one- or two-sentence Chinese story idea into a short hand-drawn picture-book video.

The workflow expands the story, creates 6-8 visual scenes, builds style-locked prompts, prepares a browser workspace for web image models, reviews keyframes, and renders a warm-paper video with a monochrome left-to-right wipe followed by synchronized text and colour.

## Quick start

```powershell
pip install -r requirements.txt
python src/run_workflow.py --story-file story.txt
```

When keyframes are missing, open `image_generation/web_model_master_instruction.txt` and paste it into a web image model once. It directs the model to create a style reference, character sheet, and every scene in one conversation. If that website cannot reuse images it created earlier, upload the two generated reference images once, then continue. Save images in the story's `keyframes/` directory and resume:

```powershell
python src/run_workflow.py --resume
```

## Image generation modes

- **Web Image Model (default):** one paste-ready master instruction for the whole story; prompt cards remain as a fallback for limited websites.
- **Image Agent (optional):** portable `keyframe_generation_tasks.json` with paths relative to the task file.

## Codex Skill

The distributable Skill is in [`skills/create-handdraw-story-video`](skills/create-handdraw-story-video). Copy that folder into your Codex skills directory, start a new Codex task, and invoke:

```text
$create-handdraw-story-video 愚公移山
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

See [`WORKFLOW_DESIGN.md`](WORKFLOW_DESIGN.md) for architecture and [`WORKFLOW_QUICKSTART.md`](WORKFLOW_QUICKSTART.md) for the Chinese quick start.
