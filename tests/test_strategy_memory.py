"""
Tests for agent/tools/strategy_memory.py

Test A: reads a UTF-8 file (including a non-ASCII char) and returns its text.
Test B: returns "" for a path that does not exist, without raising.
"""

from agent.tools.strategy_memory import load_strategy_memory


def test_load_strategy_memory_returns_file_content(tmp_path):
    """Test A: file exists with non-ASCII content — loader returns the full text."""
    content = "策略：買入強勢股，停損設 5%"  # Traditional Chinese + ASCII mix
    file = tmp_path / "strategy.txt"
    file.write_text(content, encoding="utf-8")

    result = load_strategy_memory(str(file))

    assert result == content


def test_load_strategy_memory_returns_empty_string_for_missing_file(tmp_path):
    """Test B: file does not exist — loader returns "" without raising."""
    missing_path = str(tmp_path / "nonexistent_strategy.txt")

    result = load_strategy_memory(missing_path)

    assert result == ""


def test_load_strategy_memory_returns_empty_string_for_unreadable_path(tmp_path):
    """Test C: path is a directory (unreadable as a file) — returns "" without raising."""
    a_dir = tmp_path / "a_directory"
    a_dir.mkdir()

    result = load_strategy_memory(str(a_dir))

    assert result == ""
