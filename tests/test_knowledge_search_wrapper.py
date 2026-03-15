import subprocess
from pathlib import Path


def test_knowledge_search_wrapper_help_works_without_runtime_setup():
    script = Path(__file__).resolve().parents[1] / "core-skills" / "knowledge-search" / "scripts" / "knowledge-search.sh"

    result = subprocess.run(
        ["bash", str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Usage: knowledge-search.sh" in result.stdout
