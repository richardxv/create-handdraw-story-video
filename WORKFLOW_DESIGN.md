# 手绘风格视频生成工作流设计（最终版）

**目标**：建立一套可复用的工作流，用户输入任意故事文本，即可生成**接近原视频手绘儿童绘本风格**的动画短视频。

**核心原则**：
- 风格尽量统一（接近原视频）
- 角色可变（不同故事不同角色）
- 动画层由故事驱动（不写死雨效）
- 输入为纯故事文本（agent 自动拆解）

---

## 1. 整体工作流

```
用户输入：纯故事文本
        ↓
[1] Story Parser（LLM）
    - 拆解成结构化场景列表
    - 提取视觉描述、动作、情绪、建议时长、环境效果
        ↓
[2] Style System（风格锁定）
    - 注入固定风格描述
    - 生成每场景的完整生图 Prompt
        ↓
[3] Keyframe Generation（Image Agent 生图）
    - 生成每场景 1 张高质量手绘关键帧
        ↓
[4] Animation Layer Engine（代码）
    - 根据场景描述动态决定需要的动画层
    - 生成雨/风/动作/粒子等叠加层
        ↓
[5] Video Assembly（代码）
    - 加载关键帧 + 动画层
    - 添加文字 + 控制时长 + 转场
    - 输出最终 MP4
```

---

## 2. Story Parser（最核心模块）

**输入**：纯故事文本  
**输出**：结构化 JSON（scenes list）

**每个场景应包含字段**：
```json
{
  "id": 1,
  "scene_name": "场景名称",
  "visual_description": "详细的画面视觉描述（供生图使用）",
  "on_screen_text": "屏幕上显示的文字",
  "duration": 4.5,
  "emotion": "warm / tense / surprising / nostalgic",
  "key_actions": ["角色动作描述"],
  "environment_effects": ["rain", "wind", "running", "none"],  // 动画层依据
  "notes": "生成时的注意事项"
}
```

**Prompt 设计要点**：
- 要求 agent 保持接近原视频的节奏（多数场景 4~5 秒）
- 提取环境效果（是否有雨、风、马跑等）
- 输出结构化 JSON，便于后续代码读取

---

## 3. Style System（风格锁定）

**目标**：让任意 Image Agent 生成的图片尽量接近参考视频的艺术风格。

**核心文件**：
- `prompts/hybrid_style_base.txt`（全局风格描述）
- 角色描述模板（每次生成时可灵活替换）

**使用方式**：
每次生成关键帧时，Prompt 结构为：

```
[hybrid_style_base.txt 内容]
+
当前场景的 visual_description
+
角色描述（如有）
```

**风格一致性技巧**（给 Image Agent 使用）：
- 固定风格描述文本
- 建议使用参考图功能（先生成 1-2 张风格参考图，后续生成时参考）
- 同一批次生成时尽量保持 seed 或参考一致

---

## 4. Animation Layer Engine（故事驱动）

**设计原则**：不写死任何特效，由 `environment_effects` 字段决定。

**可扩展的动画层模块**（示例）：

| 效果类型           | 触发条件                  | 实现方式                  | 优先级 |
|--------------------|---------------------------|---------------------------|--------|
| 雨效               | "rain" in effects         | Pillow 粒子系统           | 高     |
| 风吹草动 / 树叶    | "wind" in effects         | 简单位置/旋转插值         | 中     |
| 角色微动作         | key_actions 中有动作      | 参数插值（点头、挥手等）  | 高     |
| 物体移动（马跑等） | key_actions 中有移动      | 多帧或位置插值            | 中     |
| 纯静态             | "none" 或无特殊效果       | 仅显示关键帧              | -      |

**实现建议**：
- 把每个效果做成独立函数或类
- Animation Layer Engine 根据 `environment_effects` 动态组合
- 即使没有特效，也要保证关键帧有轻微呼吸感（可选）

---

## 5. 代码模块划分（推荐结构）

```
src/
├── story_parser.py              # 纯故事文本 → 结构化场景
├── style_prompt_builder.py      # 组合风格 Prompt
├── keyframe_manager.py          # 管理 Image Agent 生成的关键帧
├── animation_layers/            # 动画层模块（可扩展）
│   ├── rain.py
│   ├── wind.py
│   ├── character_action.py
│   └── base.py
├── video_compositor.py          # 单场景合成（关键帧 + 动画层 + 文字）
└── video_assembler.py           # 多场景连接 + 转场 + 输出最终视频
```

**推荐先开发的顺序**：
1. `story_parser.py`
2. `style_prompt_builder.py`
3. `video_compositor.py` + `video_assembler.py`（基础版）
4. `animation_layers/` 模块（按需扩展）

---

## 6. 开发路线图（建议）

**Phase 1（核心基础）**：
- 完成 Story Parser（支持纯故事文本）
- 完成风格 Prompt 构建
- 实现基础视频合成（只用关键帧 + 文字）

**Phase 2（动画层）**：
- 实现雨效模块（作为第一个故事驱动效果）
- 实现简单角色微动作
- 支持 `environment_effects` 动态加载

**Phase 3（优化与扩展）**：
- 提升 Image Agent 生图一致性（参考图、Prompt 优化）
- 添加更多动画层（风、物体移动等）
- 支持批量生成 + 模板复用
- 做成更易用的工具（命令行或简单界面）

---

## 7. 质量控制建议

- **风格一致性**：优先保证线条质感、交叉阴影、留白、氛围
- **节奏控制**：Story Parser 要尽量输出接近原视频的时长分布
- **动画克制**：不是每个场景都要有复杂动画，静态 + 轻微呼吸感往往更好
- **文字处理**：文字出现时机和手写感要自然

---

这个设计已经把你所有要求（风格统一、纯故事输入、故事驱动动画、灵活角色）都考虑进去了。

需要我现在把上面提到的几个核心 Prompt 和代码框架写出来吗？（比如 Story Parser 的完整 Prompt、animation_layers 的基础结构等）
