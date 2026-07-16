"""Convert plain Chinese story text into reusable, structured video scenes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class StoryParser:
    """Story parser with an LLM mode and a deterministic offline fallback."""

    VALID_EMOTIONS = {
        "warm", "tense", "surprising", "nostalgic", "calm", "dramatic", "joyful", "sad"
    }
    EMOTION_KEYWORDS = {
        "tense": ("紧张", "危险", "害怕", "担心", "着急", "逃", "追", "躲", "不见", "暴雨", "大雨"),
        "surprising": ("惊讶", "意外", "突然", "没想到", "奇迹", "发现", "原来"),
        "sad": ("伤心", "哭", "泪", "失去", "死亡", "孤独", "悲伤"),
        "joyful": ("高兴", "开心", "欢呼", "笑", "快乐", "活蹦乱跳", "不亦乐乎"),
        "warm": ("温暖", "拥抱", "微笑", "照顾", "帮助", "擦干", "团圆"),
        "nostalgic": ("回忆", "小时候", "曾经", "过去", "故乡", "想念", "记忆"),
        "dramatic": ("战争", "牺牲", "拯救", "命运", "高潮"),
        "calm": ("平静", "安静", "慢慢", "轻轻", "雨停", "宁静"),
    }
    EFFECT_KEYWORDS = {
        "rain": ("下雨", "大雨", "暴雨", "雨中", "雨水", "雨滴", "淋湿", "湿透"),
        "wind": ("大风", "刮风", "风吹", "风中", "树叶飘"),
        "snow": ("下雪", "雪花", "雪地", "大雪"),
        "running": ("跑", "奔跑", "逃", "追赶"),
        "horse_running": ("骑马", "骏马", "马奔", "马蹄"),
        "fire": ("火焰", "燃烧", "篝火", "烛火"),
        "falling_leaves": ("落叶", "黄叶", "叶子飘落"),
        "water_ripple": ("水面", "河面", "湖面", "涟漪", "波纹", "水洼"),
    }
    ACTION_WORDS = (
        "寻找", "发现", "喂鸡", "赶鸡", "躲藏", "抱回", "擦干", "撑伞", "奔跑", "追赶",
        "逃跑", "走", "跑", "跳", "哭", "笑", "说", "看", "听", "抱", "推", "拉", "坐", "站"
    )

    def __init__(self, prompt_template_path: Optional[str] = None):
        self.root = Path(__file__).resolve().parent.parent
        self.prompt_template_path = (
            Path(prompt_template_path) if prompt_template_path
            else self.root / "prompts" / "story_parser_prompt.txt"
        )

    def load_prompt_template(self) -> str:
        if not self.prompt_template_path.exists():
            raise FileNotFoundError(f"Prompt 模板不存在：{self.prompt_template_path}")
        return self.prompt_template_path.read_text(encoding="utf-8")

    def build_llm_prompt(self, story_text: str) -> str:
        template = self.load_prompt_template()
        placeholders = ("【在这里插入故事文本】", "{{STORY_TEXT}}", "{story_text}")
        for placeholder in placeholders:
            if placeholder in template:
                return template.replace(placeholder, story_text)
        return f"{template.rstrip()}\n\n故事原文：\n{story_text.strip()}"

    def parse(
        self,
        story_text: str,
        mode: str = "auto",
        llm_client: Optional[Callable[[str], str]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(story_text, str) or not story_text.strip():
            raise ValueError("故事文本不能为空")
        if mode not in {"auto", "llm", "rules"}:
            raise ValueError(f"不支持的解析模式：{mode}")
        if mode == "llm" and llm_client is None:
            raise ValueError("mode='llm' 时必须提供 llm_client")
        if mode in {"auto", "llm"} and llm_client is not None:
            try:
                return self.fix_common_issues(self._parse_with_llm(story_text, llm_client))
            except Exception:
                if mode == "llm":
                    raise
        return self.parse_with_rules(story_text)

    def _parse_with_llm(self, story_text: str, llm_client: Callable[[str], str]) -> Dict[str, Any]:
        result = self._extract_json(llm_client(self.build_llm_prompt(story_text)))
        if not isinstance(result, dict):
            raise ValueError("LLM 返回值必须是 JSON 对象")
        return result

    def _extract_json(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        for match in re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE):
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                pass
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise ValueError("无法从 LLM 响应中提取有效 JSON")

    def parse_with_rules(self, story_text: str) -> Dict[str, Any]:
        text = self._clean_text(story_text)
        segments = self._split_into_segments(text)
        scenes = [self._segment_to_scene(i, segment) for i, segment in enumerate(segments, 1)]
        return self.fix_common_issues({
            "story_title": self._extract_title(text),
            "total_duration_estimate": round(sum(s["duration"] for s in scenes), 1),
            "scenes": scenes,
        })

    @staticmethod
    def _clean_text(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _split_into_segments(self, text: str) -> List[str]:
        sentences = [s.strip() for s in re.findall(r"[^。！？!?；;\n]+[。！？!?；;]?", text) if s.strip()]
        clauses: List[str] = []
        split_markers = re.compile(r"(?=有一天|突然|后来|最后|雨停后|第二天|几天后|从此|这时)")
        for sentence in sentences:
            parts = [p.strip(" ，,") for p in split_markers.split(sentence) if p.strip(" ，,")]
            clauses.extend(parts)
        if not clauses:
            return [text]

        # Merge fragments while preserving story beats. 18–46 Chinese characters is a useful
        # range for one 4–6 second illustrated scene.
        # A short sentence can still be an important visual beat (for example, "雨停了").
        # Keep explicit sentence/event boundaries; only split segments that are too long.
        merged: List[str] = clauses
        final: List[str] = []
        for segment in merged:
            if len(segment) <= 52:
                final.append(segment)
                continue
            parts = [p for p in re.split(r"(?<=[，,])", segment) if p]
            current = ""
            for part in parts:
                if current and len(current) + len(part) > 42:
                    final.append(current.strip())
                    current = part
                else:
                    current += part
            if current.strip():
                final.append(current.strip())
        return final[:12]

    @staticmethod
    def _extract_title(text: str) -> str:
        quoted = re.search(r"[《“\"]([^》”\"]{2,20})[》”\"]", text)
        if quoted:
            return quoted.group(1)
        if "小时候" in text or "记忆" in text:
            return "童年的记忆"
        first = re.sub(r"[，。！？；,.!?;\s]", "", text)[:8]
        return first or "手绘故事"

    def _segment_to_scene(self, idx: int, text: str) -> Dict[str, Any]:
        emotion = self._infer_emotion(text)
        effects = self._infer_effects(text)
        actions = self._extract_actions(text)
        return {
            "id": idx,
            "scene_name": self._generate_scene_name(text, idx),
            "visual_description": self._generate_visual_description(text, emotion, effects, actions),
            "on_screen_text": text.rstrip("。！？!?；;"),
            "duration": self._calculate_duration(text, emotion),
            "emotion": emotion,
            "key_actions": actions,
            "environment_effects": effects or ["none"],
            "notes": f"规则解析生成的场景 {idx}；生成关键帧时不要在画面内绘制文字。",
        }

    def _infer_emotion(self, text: str) -> str:
        scores = {k: sum(text.count(word) for word in words) for k, words in self.EMOTION_KEYWORDS.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] else "calm"

    def _infer_effects(self, text: str) -> List[str]:
        effects = [name for name, words in self.EFFECT_KEYWORDS.items() if any(w in text for w in words)]
        if any(stop in text for stop in ("雨停", "雨过天晴", "不再下雨")):
            effects = [effect for effect in effects if effect != "rain"]
            if "水洼" in text and "water_ripple" not in effects:
                effects.append("water_ripple")
        return effects

    def _extract_actions(self, text: str) -> List[str]:
        found = []
        for action in self.ACTION_WORDS:
            if action in text and not any(action in existing for existing in found):
                subject = "小鸡" if "鸡" in text and action in {"躲藏", "跑", "跳"} else "角色"
                found.append(f"{subject}{action}")
        return found[:3] or ["角色自然静立或轻微呼吸"]

    @staticmethod
    def _generate_scene_name(text: str, idx: int) -> str:
        markers = (
            ("小时候", "童年开场"), ("喂鸡", "院中喂鸡"), ("大雨", "骤雨来临"),
            ("寻找", "雨中寻找"), ("发现", "找到小鸡"), ("擦干", "温柔照料"),
            ("雨停", "雨后新晴"), ("记忆", "珍藏记忆"),
        )
        for marker, name in markers:
            if marker in text:
                return name
        clean = re.sub(r"[，。！？；,.!?;\s]", "", text)
        return clean[:8] or f"场景{idx}"

    @staticmethod
    def _calculate_duration(text: str, emotion: str) -> float:
        readable_chars = len(re.sub(r"\s|[，。！？；,.!?;]", "", text))
        duration = 3.5 + readable_chars / 14.0
        if emotion in {"tense", "dramatic"}:
            duration += 0.3
        return round(min(6.5, max(4.0, duration)), 1)

    @staticmethod
    def _generate_visual_description(text: str, emotion: str, effects: List[str], actions: List[str]) -> str:
        subjects = []
        for token, desc in (
            ("奶奶", "a kind grandmother with gray hair tied in a bun"),
            ("小黄鸡", "a tiny wet yellow chick"),
            ("小鸡", "a group of round yellow chicks"),
            ("我", "a young child narrator"),
            ("马", "a simple hand-drawn horse"),
        ):
            if token in text and desc not in subjects:
                subjects.append(desc)
        setting = "a quiet traditional rural courtyard" if any(x in text for x in ("院子", "奶奶家", "柴堆", "鸡")) else "a simple storybook setting"
        weather = {
            "rain": "diagonal rain, wet ground and restrained reflections",
            "wind": "soft wind moving leaves and clothing",
            "snow": "sparse snowflakes and a pale winter ground",
            "water_ripple": "small puddles with delicate ripples",
        }
        effect_desc = [weather[e] for e in effects if e in weather]
        mood = {
            "warm": "tender warm light and caring body language",
            "tense": "dramatic but child-friendly tension",
            "surprising": "a clear moment of discovery",
            "nostalgic": "soft nostalgic afternoon light",
            "joyful": "bright cheerful energy",
            "sad": "quiet melancholy with gentle expressions",
            "dramatic": "strong restrained contrast",
            "calm": "peaceful natural light",
        }[emotion]
        content = ", ".join(subjects) if subjects else "simple expressive story characters"
        action_desc = "; ".join(actions)
        return (
            f"{content} in {setting}, {action_desc}, {mood}"
            + (f", {', '.join(effect_desc)}" if effect_desc else "")
            + ", clear single story beat, readable silhouettes, vertical composition, no written text in image"
        )

    def validate_scenes(self, data: Dict[str, Any]) -> bool:
        if not isinstance(data, dict) or not isinstance(data.get("scenes"), list) or not data["scenes"]:
            return False
        required = {"id", "scene_name", "visual_description", "on_screen_text", "duration", "emotion", "key_actions", "environment_effects", "notes"}
        return all(
            isinstance(scene, dict)
            and required.issubset(scene)
            and scene["emotion"] in self.VALID_EMOTIONS
            and 2.0 <= float(scene["duration"]) <= 8.0
            for scene in data["scenes"]
        )

    def fix_common_issues(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            data = {}
        scenes = data.get("scenes") if isinstance(data.get("scenes"), list) else []
        fixed = []
        defaults = {
            "scene_name": "未命名场景", "visual_description": "simple hand-drawn storybook scene",
            "on_screen_text": "", "emotion": "calm", "key_actions": [],
            "environment_effects": ["none"], "notes": "",
        }
        for idx, scene in enumerate(scenes, 1):
            if not isinstance(scene, dict):
                continue
            item = {**defaults, **scene, "id": idx}
            item["emotion"] = item["emotion"] if item["emotion"] in self.VALID_EMOTIONS else "calm"
            try:
                item["duration"] = round(min(8.0, max(2.0, float(item.get("duration", 4.5)))), 1)
            except (TypeError, ValueError):
                item["duration"] = 4.5
            for key in ("key_actions", "environment_effects"):
                if not isinstance(item[key], list):
                    item[key] = []
            item["environment_effects"] = item["environment_effects"] or ["none"]
            fixed.append(item)
        data["story_title"] = str(data.get("story_title") or "手绘故事")
        data["scenes"] = fixed
        data["total_duration_estimate"] = round(sum(s["duration"] for s in fixed), 1)
        return data

    def save_scenes(self, data: Dict[str, Any], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[StoryParser] 场景数据已保存：{path}")

    def print_summary(self, data: Dict[str, Any]) -> None:
        print(f"故事：{data.get('story_title', '未命名')}｜场景：{len(data.get('scenes', []))}｜预计时长：{data.get('total_duration_estimate', 0)} 秒")
        for scene in data.get("scenes", []):
            print(f"[{scene['id']:02d}] {scene['scene_name']} | {scene['duration']}s | {scene['emotion']} | {', '.join(scene['environment_effects'])}")


if __name__ == "__main__":
    parser = StoryParser()
    demo_story = "小时候，我常住在奶奶家。突然下起大雨，一只小黄鸡不见了。我撑伞寻找，最后在柴堆后发现了它。雨停后，小鸡又活蹦乱跳。"
    result = parser.parse(demo_story, mode="rules")
    parser.print_summary(result)
    parser.save_scenes(result, str(parser.root / "output" / "parsed_scenes_demo.json"))
