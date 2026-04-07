"""Prompt模板 - 语义分段"""
from configs.settings import get_settings

settings = get_settings()


SEGMENT_PROMPT = """你是一个视频内容分析专家。请分析以下ASR转录文本，将其划分为语义完整的段落。

## 输入文本
{text}

## 分段要求
1. 每个段落应该是一个完整的话题或主题
2. 段落边界应该自然，不要打断完整的句子
3. 给每个段落标注类型和重要性

## 输出格式（JSON）
请返回以下格式的JSON：
{
  "segments": [
    {
      "id": "seg_001",
      "start": 开始时间（秒）,
      "end": 结束时间（秒）,
      "text": "段落文本",
      "importance": 重要性评分（0-1）,
      "type": "段落类型：核心观点/操作演示/情绪表达/背景信息/数据分析/UI操作",
      "need_vision": 是否需要视觉分析（true/false）
    }
  ],
  "summary": "整体内容摘要"
}

## 视觉需求判定规则
如果文本包含以下内容，need_vision应设为true：
- UI操作描述（点击、滑动、输入等）
- 图表或数据可视化描述
- 实物展示或演示操作
- 界面布局描述
- 非语言信息（表情、动作、姿态）

请开始分析。
"""


SEGMENT_IMPORTANCE_PROMPT = """请对以下视频段落进行重要性评分。

## 段落信息
文本：{text}
类型：{type}
时长：{duration}秒

## 评分维度
1. 信息量（0-0.4）：内容的信息密度和价值
2. 独特性（0-0.3）：是否包含独特见解或关键信息
3. 相关性（0-0.3）：与主题的相关程度

## 输出格式（JSON）
{
  "importance": 总评分（0-1）,
  "scores": {
    "information": 信息量评分,
    "uniqueness": 独特性评分,
    "relevance": 相关性评分
  },
  "reason": "评分理由"
}

请开始评分。
"""