# Story Parser 示例

## 示例输入（纯故事文本）

古时候，北方边塞住着一个人，人们叫他塞翁。
一天，他的马跑进了胡人的地界，邻居都来安慰。
塞翁却说：“这怎么知道不是福呢？”
几个月后，那匹马竟带着一匹好马回来，邻居们前来祝贺。
塞翁又说：“这怎么知道不是祸呢？”
不久，塞翁的儿子骑新马摔断了腿，邻居又来安慰。
后来胡人大举入侵，年轻人都被征召作战，许多人战死；
塞翁的儿子因为腿伤没有去参战，得以保全性命。

## 示例输出（结构化场景）

```json
{
  "story_title": "塞翁失马",
  "total_duration_estimate": 52,
  "scenes": [
    {
      "id": 1,
      "scene_name": "开场介绍塞翁",
      "visual_description": "古代北方边塞，简陋的房屋和木栅栏。一个慈祥的老人站在院子里，背景是荒凉的山丘和草原。温暖怀旧的手绘风格，松散墨线，交叉阴影。",
      "on_screen_text": "古时候，北方边塞住着一个人，人们叫他塞翁。",
      "duration": 5.0,
      "emotion": "calm",
      "key_actions": ["老人站在院子里"],
      "environment_effects": ["none"],
      "notes": "建立故事背景和人物"
    },
    {
      "id": 2,
      "scene_name": "马跑进胡人地界",
      "visual_description": "一匹马越过木栅栏跑向远方，远处是胡人地界的山丘。老人站在栅栏边看着。手绘风格，动态感，留白较多。",
      "on_screen_text": "一天，他的马跑进了胡人的地界，邻居都来安慰。",
      "duration": 4.5,
      "emotion": "tense",
      "key_actions": ["马跑远", "老人看着"],
      "environment_effects": ["running"],
      "notes": "制造悬念"
    },
    {
      "id": 3,
      "scene_name": "塞翁说可能是福",
      "visual_description": "塞翁平静地站在院子里，对前来安慰的邻居说话。邻居表情惊讶。温暖的手绘风格，重点在人物表情和对话感。",
      "on_screen_text": "塞翁却说：“这怎么知道不是福呢？”",
      "duration": 5.0,
      "emotion": "calm",
      "key_actions": ["塞翁说话", "邻居惊讶"],
      "environment_effects": ["none"],
      "notes": "体现塞翁的豁达"
    },
    {
      "id": 4,
      "scene_name": "马带好马回来",
      "visual_description": "塞翁的马带着一匹漂亮的好马一起回来。邻居们围在旁边祝贺。动态且喜庆的手绘画面。",
      "on_screen_text": "几个月后，那匹马竟带着一匹好马回来，邻居们前来祝贺。",
      "duration": 5.0,
      "emotion": "surprising",
      "key_actions": ["两匹马回来", "邻居祝贺"],
      "environment_effects": ["horse_running"],
      "notes": "转折点，情绪上扬"
    },
    {
      "id": 5,
      "scene_name": "塞翁说可能是祸",
      "visual_description": "塞翁依然平静地对邻居说话，邻居们表情复杂。手绘风格，重点表现人物神态。",
      "on_screen_text": "塞翁又说：“这怎么知道不是祸呢？”",
      "duration": 4.5,
      "emotion": "calm",
      "key_actions": ["塞翁说话"],
      "environment_effects": ["none"],
      "notes": "再次体现哲学态度"
    },
    {
      "id": 6,
      "scene_name": "儿子摔断腿",
      "visual_description": "塞翁的儿子从马上摔下来，腿部受伤。塞翁蹲下来安慰儿子。紧张且温情的手绘画面。",
      "on_screen_text": "不久，塞翁的儿子骑新马摔断了腿，邻居又来安慰。",
      "duration": 5.0,
      "emotion": "tense",
      "key_actions": ["儿子摔倒", "塞翁安慰"],
      "environment_effects": ["none"],
      "notes": "坏事发生"
    },
    {
      "id": 7,
      "scene_name": "胡人入侵，儿子幸免",
      "visual_description": "远处胡人军队入侵的场景，年轻人都被征召。塞翁的儿子因为腿伤留在家中，和塞翁站在一起。手绘风格，远景与近景结合，情感强烈。",
      "on_screen_text": "后来胡人大举入侵，年轻人都被征召作战，许多人战死；塞翁的儿子因为腿伤没有去参战，得以保全性命。",
      "duration": 6.0,
      "emotion": "dramatic",
      "key_actions": ["军队远去", "父子站在一起"],
      "environment_effects": ["none"],
      "notes": "高潮与结局，体现福祸相依"
    },
    {
      "id": 8,
      "scene_name": "结尾升华",
      "visual_description": "塞翁和儿子站在院子里，背景是边塞的山丘和房屋。温暖而带有哲理意味的手绘画面，适合作为结尾。",
      "on_screen_text": "塞翁失马，焉知非福",
      "duration": 5.0,
      "emotion": "nostalgic",
      "key_actions": ["父子站在一起"],
      "environment_effects": ["none"],
      "notes": "故事升华，留白结尾"
    }
  ]
}
```