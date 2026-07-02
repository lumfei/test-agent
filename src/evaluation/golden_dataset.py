"""
Golden dataset loader for evaluation.
Each case: spec_url, expected_bugs (known bugs to detect), min_pass_rate, max_pass_rate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GoldenCase:
    """A single golden test case."""
    id: str
    name: str
    description: str
    spec_url: str
    spec_type: str = "openapi"  # openapi / swagger / html
    expected_bugs: list[str] = field(default_factory=list)
    min_pass_rate: float = 0.0
    max_pass_rate: float = 100.0
    expected_endpoints_min: int = 0
    tags: list[str] = field(default_factory=list)


@dataclass
class GoldenDataset:
    """Collection of golden test cases for evaluation."""
    cases: list[GoldenCase] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.cases)

    @classmethod
    def load(cls, path: str | None = None) -> GoldenDataset:
        if path is None:
            path = Path(__file__).parent.parent.parent / "tests" / "golden_dataset.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cases = []
        for item in data.get("cases", []):
            cases.append(GoldenCase(
                id=item["id"],
                name=item["name"],
                description=item.get("description", ""),
                spec_url=item["spec_url"],
                spec_type=item.get("spec_type", "openapi"),
                expected_bugs=item.get("expected_bugs", []),
                min_pass_rate=item.get("min_pass_rate", 0.0),
                max_pass_rate=item.get("max_pass_rate", 100.0),
                expected_endpoints_min=item.get("expected_endpoints_min", 0),
                tags=item.get("tags", []),
            ))

        return cls(cases=cases, metadata=data.get("metadata", {}))


# Pre-built golden dataset for mock API evaluation
def build_mock_golden() -> GoldenDataset:
    return GoldenDataset(
        metadata={"name": "Mock API Golden Dataset", "version": "1.0"},
        cases=[
            GoldenCase(
                id="mock-001",
                name="Mock Buggy API — full suite",
                description="Test against mock API with 5 known bugs",
                spec_url="http://localhost:8003/openapi.json",
                expected_bugs=[
                    "limit=0 causes 500",
                    "empty body accepted",
                    "id=999 returns HTML",
                    "no auth on DELETE",
                    "SQL injection not escaped",
                ],
                min_pass_rate=5.0,
                max_pass_rate=40.0,
                expected_endpoints_min=5,
                tags=["mock", "bug-detection"],
            ),
        ],
    )
