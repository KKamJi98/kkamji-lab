"""Tests for renumber_readme.renumber_headers()."""

import sys
from pathlib import Path


# renumber_readme.py is a top-level script (no package).
# Add the parent directory to sys.path so we can import it directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

from renumber_readme import renumber_headers  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(tmp_path: Path, content: str) -> str:
    """Write *content* to a temp file, run renumber_headers, return result."""
    f = tmp_path / "test.md"
    f.write_text(content, encoding="utf-8")
    renumber_headers(str(f))
    return f.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 기본 헤더 번호 매기기
# ---------------------------------------------------------------------------


def test_h2_gets_numbered(tmp_path):
    """H2 헤더에 '1.' 번호가 붙어야 한다."""
    result = _run(tmp_path, "## Introduction\n")
    assert result.startswith("## 1. Introduction")


def test_h3_gets_nested_number(tmp_path):
    """H3 헤더는 'N.M.' 형식의 중첩 번호를 받아야 한다."""
    content = "## Section\n### Subsection\n"
    result = _run(tmp_path, content)
    lines = result.splitlines()
    assert lines[0] == "## 1. Section"
    assert lines[1] == "### 1.1. Subsection"


def test_h4_gets_three_level_number(tmp_path):
    """H4 헤더는 'N.M.K.' 형식 세 단계 번호를 받아야 한다."""
    content = "## A\n### B\n#### C\n"
    result = _run(tmp_path, content)
    lines = result.splitlines()
    assert lines[0] == "## 1. A"
    assert lines[1] == "### 1.1. B"
    assert lines[2] == "#### 1.1.1. C"


def test_multiple_h2_increment_independently(tmp_path):
    """H2가 여러 개면 독립적으로 1, 2, 3... 번호를 가져야 한다."""
    content = "## Alpha\n## Beta\n## Gamma\n"
    result = _run(tmp_path, content)
    lines = result.splitlines()
    assert lines[0] == "## 1. Alpha"
    assert lines[1] == "## 2. Beta"
    assert lines[2] == "## 3. Gamma"


def test_existing_number_is_replaced(tmp_path):
    """이미 번호가 붙은 헤더는 새로운 번호로 교체되어야 한다."""
    content = "## 99. OldNumber\n"
    result = _run(tmp_path, content)
    assert result.startswith("## 1. OldNumber")


# ---------------------------------------------------------------------------
# BOM 처리
# ---------------------------------------------------------------------------


def test_bom_is_stripped_from_output(tmp_path):
    """UTF-8 BOM이 포함된 입력 파일을 처리한 결과에는 BOM이 없어야 한다."""
    f = tmp_path / "test.md"
    # utf-8-sig 인코딩으로 쓰면 파일 앞에 BOM이 삽입된다
    f.write_text("## Title\n", encoding="utf-8-sig")
    renumber_headers(str(f))
    raw = f.read_bytes()
    # BOM(\xef\xbb\xbf)이 없어야 한다
    assert not raw.startswith(b"\xef\xbb\xbf")


# ---------------------------------------------------------------------------
# 코드 블록 내 헤더 패턴 무시
# ---------------------------------------------------------------------------


def test_fenced_code_block_headers_are_ignored(tmp_path):
    """``` 코드 블록 안의 ## 패턴은 번호를 붙이지 않아야 한다."""
    content = "## Real Header\n```\n## Not A Header\n```\n"
    result = _run(tmp_path, content)
    lines = result.splitlines()
    assert lines[0] == "## 1. Real Header"
    # 코드 블록 안의 줄은 그대로 유지
    assert lines[1] == "```"
    assert lines[2] == "## Not A Header"
    assert lines[3] == "```"


def test_fenced_code_block_toggle_restores_numbering(tmp_path):
    """코드 블록 이후에 나오는 실제 헤더에는 번호가 정상 부여되어야 한다."""
    content = "## Before\n```\n## Inside\n```\n## After\n"
    result = _run(tmp_path, content)
    lines = result.splitlines()
    assert lines[0] == "## 1. Before"
    assert lines[4] == "## 2. After"


# ---------------------------------------------------------------------------
# indent 코드 블록 내 헤더 무시
# ---------------------------------------------------------------------------


def test_indented_code_block_headers_are_ignored(tmp_path):
    """4칸 이상 indent된 줄은 코드 블록으로 간주하여 번호를 붙이지 않아야 한다."""
    content = "## Section\n    ## not a header\n"
    result = _run(tmp_path, content)
    lines = result.splitlines()
    assert lines[0] == "## 1. Section"
    assert lines[1] == "    ## not a header"


# ---------------------------------------------------------------------------
# 빈 파일 처리
# ---------------------------------------------------------------------------


def test_empty_file_is_handled_without_error(tmp_path):
    """빈 파일을 처리할 때 예외가 발생하지 않아야 하며 출력도 비어 있어야 한다."""
    result = _run(tmp_path, "")
    assert result == ""


# ---------------------------------------------------------------------------
# H1 건너뛰기
# ---------------------------------------------------------------------------


def test_h1_is_not_numbered(tmp_path):
    """H1(#) 헤더에는 번호를 붙이지 않아야 한다."""
    content = "# Document Title\n## Section\n"
    result = _run(tmp_path, content)
    lines = result.splitlines()
    assert lines[0] == "# Document Title"
    assert lines[1] == "## 1. Section"


def test_h1_does_not_affect_h2_counter(tmp_path):
    """H1이 있어도 H2 카운터는 1부터 시작해야 한다."""
    content = "# Title\n## First\n## Second\n"
    result = _run(tmp_path, content)
    lines = result.splitlines()
    assert lines[1] == "## 1. First"
    assert lines[2] == "## 2. Second"
