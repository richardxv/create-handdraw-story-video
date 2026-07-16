# 手绘故事视频工作流：当前入口

当前统一入口是 `src/run_workflow.py`。默认视觉模板为暖白纸张、手写文字，以及连续的“黑白绘本画面逐渐上色”效果。

## 1. 启动一个新故事

把纯故事文本保存成 UTF-8 文件，例如 `story.txt`，然后运行：

```powershell
python src/run_workflow.py --story-file story.txt
```

程序会自动完成：

1. Story Parser 场景拆解。
2. Style Prompt Builder 生图提示词构建。
3. 关键帧存在性与尺寸检查。
4. 黑白到彩色的绘本视频合成。

## 2. 网页 AI 生图（默认）

生成浏览器生图工作台：

```powershell
python src/export_web_image_kit.py --source stories/<story-slug>/scenes_with_prompts.json
```

打开 `stories/<story-slug>/image_generation/prompt_cards.html`，先生成风格参考图和角色设定图，再逐幕复制 Prompt。每一幕都上传相同的两张参考图。

## 3. Image Agent 关键帧断点（可选）

如果图片不齐，流程会停在 `keyframes_pending`，并生成：

`output/keyframe_generation_tasks.json`

让任意具备生图和文件读写能力的 Image Agent 按任务文件生成图片，并保存为：

`assets/keyframes/scene_01.png`、`scene_02.png`……

图片生成完成后继续：

```powershell
python src/run_workflow.py --resume
```

## 3. 状态与结果

`output/workflow_status.json` 始终记录当前阶段：

- `keyframes_pending`：等待关键帧。
- `rendering`：正在合成。
- `complete`：最终 MP4 已完成。

默认正式成片路径为 `output/story_video_latest.mp4`。工作流不会额外生成名为 Demo 的视频。

建议关键帧使用 3:4 竖图。非 3:4 图片可以被安全适配，但会记录为质量警告。
