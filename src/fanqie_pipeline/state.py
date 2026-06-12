from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class CompletedUnit:
    """已完成的生成单元。短故事叫 segment，长篇可以叫 chapter。"""

    number: int
    path: str
    char_count: int
    quality_passed: bool


@dataclass
class GenerationState:
    """可恢复生成状态。

    这个文件是长篇稳定性的核心：进程崩了、手动 Ctrl+C、电脑重启后，
    只要输出目录还在，就能知道下一次从哪里继续。
    """

    book_id: str
    book_type: str
    style: str
    target_words: int
    unit_words: int
    total_units: int
    next_unit: int = 1
    status: str = "running"
    current_chars: int = 0
    completed_units: List[CompletedUnit] = field(default_factory=list)
    last_error: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        return self.next_unit > self.total_units or self.current_chars >= self.target_words

    @classmethod
    def create(
        cls,
        book_id: str,
        book_type: str,
        style: str,
        target_words: int,
        unit_words: int,
        total_units: int,
    ) -> "GenerationState":
        return cls(
            book_id=book_id,
            book_type=book_type,
            style=style,
            target_words=target_words,
            unit_words=unit_words,
            total_units=total_units,
        )

    @classmethod
    def load(cls, path: Path) -> "GenerationState":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["completed_units"] = [CompletedUnit(**item) for item in data.get("completed_units", [])]
        return cls(**data)

    def record_unit(self, number: int, path: Path, char_count: int, quality_passed: bool) -> None:
        self.completed_units.append(
            CompletedUnit(
                number=number,
                path=str(path),
                char_count=char_count,
                quality_passed=quality_passed,
            )
        )
        self.current_chars += char_count
        self.next_unit = number + 1
        self.status = "complete" if self.is_complete else "running"
        self.last_error = None

    def mark_paused(self) -> None:
        self.status = "paused"

    def mark_error(self, message: str) -> None:
        self.status = "error"
        self.last_error = message

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
