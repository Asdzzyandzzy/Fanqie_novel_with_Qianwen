from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .planner import StoryPlan


@dataclass
class OutlineIssue:
    level: str
    message: str


@dataclass
class OutlineReport:
    issues: List[OutlineIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)


def inspect_outline(plan: StoryPlan, target_words: int, unit_count: int) -> OutlineReport:
    """检查大纲是否足够支撑目标字数。

    百万字项目不是靠一个短篇模板硬撑。这里先做硬性报警：
    目标越长，必须有更多阶段、钩子和反转，否则后期会注水或崩线。
    """

    report = OutlineReport()
    if target_words >= 300_000 and len(plan.reversals) < 8:
        report.issues.append(OutlineIssue("warning", "长篇目标较大，但反转节点少于8个，后期可能重复。"))
    if target_words >= 1_000_000 and unit_count < 200:
        report.issues.append(OutlineIssue("warning", "百万字建议至少200个生成单元，否则单元过长、失败恢复成本高。"))
    if len(plan.full_beats) < 10:
        report.issues.append(OutlineIssue("warning", "全篇爽点规划偏少，长线生成容易变平。"))
    if "第一人称" not in plan.protagonist:
        report.issues.append(OutlineIssue("warning", "主角设定没有明确第一人称，代入稳定性可能下降。"))
    if not plan.ending_hook:
        report.issues.append(OutlineIssue("error", "缺少结尾钩子。"))
    return report


def write_outline_report(path: Path, report: OutlineReport) -> None:
    lines = ["# Outline Report", "", f"Passed: {report.passed}", ""]
    if report.issues:
        lines.append("Issues:")
        for issue in report.issues:
            lines.append(f"- [{issue.level}] {issue.message}")
    else:
        lines.append("Issues: none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
