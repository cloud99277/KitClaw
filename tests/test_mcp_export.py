import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "core-skills" / "mcp-export" / "scripts" / "export-mcp.py"

spec = importlib.util.spec_from_file_location("kitclaw_mcp_export", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load module spec for {SCRIPT_PATH}")
mcp_export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp_export)


def write_skill(root: Path, name: str, description: str, io_block: str = "") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                io_block,
                "---",
                "",
                f"# {name}",
            ]
        ).replace("\n\n---", "\n---"),
        encoding="utf-8",
    )


def test_discover_skills_reads_frontmatter(tmp_path):
    write_skill(
        tmp_path,
        "sample-skill",
        "Sample description",
        "\n".join(
            [
                "io:",
                "  input:",
                "    - type: text",
                "      description: input text",
                "  output:",
                "    - type: json_data",
                "      description: output json",
            ]
        ),
    )

    discovered = mcp_export.discover_skills(tmp_path)

    assert len(discovered) == 1
    skill_dir, frontmatter = discovered[0]
    assert skill_dir.name == "sample-skill"
    assert frontmatter["name"] == "sample-skill"
    assert frontmatter["io"]["input"][0]["type"] == "text"


def test_skill_to_tool_builds_input_schema(tmp_path):
    write_skill(
        tmp_path,
        "query-skill",
        "Query a KB",
        "\n".join(
            [
                "io:",
                "  input:",
                "    - type: url",
                "      description: target url",
                "      required: false",
            ]
        ),
    )

    discovered = mcp_export.discover_skills(tmp_path)
    tool = mcp_export.skill_to_tool(*discovered[0])

    assert tool["name"] == "query-skill"
    assert tool["inputSchema"]["properties"]["input_0_url"]["format"] == "uri"
    assert "required" not in tool["inputSchema"]


def test_cli_outputs_json(tmp_path):
    write_skill(tmp_path, "alpha", "Alpha skill")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--skills-dir", str(tmp_path), "--pretty"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["stats"]["total_skills"] == 1
    assert payload["tools"][0]["name"] == "alpha"
