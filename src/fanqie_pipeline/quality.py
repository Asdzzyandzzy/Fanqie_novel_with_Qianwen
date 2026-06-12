from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class QualityIssue:
    level: str
    message: str


@dataclass
class SegmentQualityReport:
    segment_number: int
    char_count: int
    issues: List[QualityIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)


def inspect_segment(
    text: str,
    segment_number: int,
    min_chars: int,
    previous_tail: str,
    first_person_required: bool = True,
) -> SegmentQualityReport:
    report = SegmentQualityReport(segment_number=segment_number, char_count=len(text))
    stripped = text.strip()

    if len(stripped) < min_chars:
        report.issues.append(QualityIssue("error", f"长度不足：{len(stripped)} < {min_chars}。"))

    if any(marker in stripped[:120] for marker in ["第1章", "第一章", "章节", "大纲", "分析"]):
        report.issues.append(QualityIssue("warning", "开头疑似包含章节标题或说明文字。"))

    lazy_markers = ["由于篇幅限制", "以下是", "故事大纲", "创作思路", "待续", "未完待续", "这一章主要", "本章主要"]
    if any(marker in stripped for marker in lazy_markers):
        report.issues.append(QualityIssue("error", "检测到偷懒/说明性输出，不是纯正文。"))

    if first_person_required and "我" not in stripped[:500]:
        report.issues.append(QualityIssue("warning", "前500字缺少第一人称“我”，代入感可能不足。"))

    if segment_number == 1 and not _has_opening_conflict(stripped[:300]):
        report.issues.append(QualityIssue("warning", "前300字冲突信号偏弱。"))

    if segment_number > 1 and previous_tail:
        previous_keywords = _extract_keywords(previous_tail)
        if previous_keywords and not any(word in stripped[:500] for word in previous_keywords):
            report.issues.append(QualityIssue("warning", "本段开头与上一段关键词衔接弱，可能跳场。"))

    if stripped.count("。") + stripped.count("！") + stripped.count("？") < 8:
        report.issues.append(QualityIssue("warning", "句子数量偏少，可能没有充分展开。"))

    dialogue_count = stripped.count("“") + stripped.count('"')
    if dialogue_count < 4:
        report.issues.append(QualityIssue("warning", "对白偏少，信息流推进可能不够快。"))

    paragraphs = [item.strip() for item in stripped.splitlines() if item.strip()]
    if len(paragraphs) >= 4 and len(set(paragraphs)) <= len(paragraphs) // 2:
        report.issues.append(QualityIssue("error", "段落重复率过高。"))

    return report


def append_quality_report(path: Path, report: SegmentQualityReport) -> None:
    lines = [
        f"## Segment {report.segment_number}",
        "",
        f"- Characters: {report.char_count}",
        f"- Passed: {report.passed}",
    ]
    if report.issues:
        lines.append("- Issues:")
        for issue in report.issues:
            lines.append(f"  - [{issue.level}] {issue.message}")
    else:
        lines.append("- Issues: none")
    lines.append("")
    with path.open("a", encoding="utf-8") as file:
        file.write("\n".join(lines))


def _has_opening_conflict(text: str) -> bool:
    signals = [
        "离婚",
        "背叛",
        "滚",
        "签字",
        "打脸",
        "白月光",
        "羞辱",
        "跪",
        "破产",
        "证据",
        "威胁",
        "捉奸",
    ]
    return any(signal in text for signal in signals)


def _extract_keywords(text: str) -> List[str]:
    candidates = ["离婚", "协议", "白月光", "证据", "录音", "女主", "反派", "机场", "集团", "身份", "真相", "跪"]
    return [word for word in candidates if word in text]
