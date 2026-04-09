"""Prompt模板 - 多模态融合"""
ALIGNMENT_PROMPT = """请判断文本描述与视觉发现是否一致。

## 文本描述
{text}

## 视觉发现
视觉摘要：{vision_summary}
识别的动作：{actions}
识别的物体：{objects}

## 对齐任务
判断文本描述的内容是否与视觉分析结果相符。

## 输出格式（JSON）
{{
  "status": "consistent/conflict/insufficient",
  "reason": "判断原因",
  "text_claim": "文本中的关键描述",
  "vision_finding": "视觉分析的关键发现",
  "corrections": ["如果存在冲突，建议的修正"]
}}

请开始对齐分析。
"""


FUSION_PROMPT = """请将文本分析和视觉分析结果进行融合，生成最终的高亮片段。

## 文本分析结果
{text_result}

## 视觉分析结果
{vision_result}

## 融合任务
1. 整合文本和视觉信息
2. 解决可能的冲突
3. 生成完整的内容描述
4. 确定片段的高亮程度

## 输出格式（JSON）
{{
  "type": "片段类型",
  "text": "文本描述",
  "visual_explanation": "视觉补充说明",
  "time": [开始时间, 结束时间],
  "importance": 重要性评分（0-1）,
  "confidence": 置信度（0-1）
}}

请开始融合分析。
"""