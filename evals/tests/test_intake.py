from pathlib import Path

import pytest

from evals.intake import extract


def test_intake_rejects_missing_steps(tmp_path: Path):
    source = tmp_path / "partial.md"
    source.write_text("## 17. 十条需求链的填写内容\n### 17.2 chain-01：item_validation（dev）\n")
    with pytest.raises(ValueError, match="ten preregistered topics"):
        extract(source)
