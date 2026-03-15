import json
import os
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "core-skills" / "conversation-distiller" / "scripts" / "save_note.py"

spec = spec_from_file_location("conversation_distiller_save_note", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load module spec for {SCRIPT_PATH}")
save_note = module_from_spec(spec)
spec.loader.exec_module(save_note)


def write_memory_config(home: Path, l3_paths: list[str]) -> None:
    memory_dir = home / ".ai-memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "config.json").write_text(
        json.dumps({"schema_version": "1.0", "l3_paths": l3_paths}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_resolve_base_dir_uses_first_configured_l3_path(monkeypatch, tmp_path):
    home = tmp_path / "home"
    knowledge_root = tmp_path / "knowledge-base"
    knowledge_root.mkdir()
    home.mkdir()
    write_memory_config(home, [str(knowledge_root)])
    monkeypatch.setenv("HOME", str(home))

    resolved = save_note.resolve_base_dir("")

    assert resolved == str(knowledge_root / "40_Agent_Notes" / "distilled-conversations")


def test_resolve_knowledge_root_prefers_matching_configured_parent(monkeypatch, tmp_path):
    home = tmp_path / "home"
    vault_a = tmp_path / "vault-a"
    vault_b = tmp_path / "vault-b"
    note = vault_b / "40_Agent_Notes" / "distilled-conversations" / "dev" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("x", encoding="utf-8")
    home.mkdir()
    vault_a.mkdir()
    vault_b.mkdir(exist_ok=True)
    write_memory_config(home, [str(vault_a), str(vault_b)])
    monkeypatch.setenv("HOME", str(home))

    root = save_note.resolve_knowledge_root(str(note))

    assert root == str(vault_b)


def test_save_creates_category_subfolder_and_markdown_content(monkeypatch, tmp_path):
    home = tmp_path / "home"
    knowledge_root = tmp_path / "knowledge-base"
    knowledge_root.mkdir()
    home.mkdir()
    write_memory_config(home, [str(knowledge_root)])
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv(save_note.AUTO_INGEST_ENV, "false")

    path, generated_at, ingest = save_note.save("[Dev] Unit Test Note", "### Core\nbody", "")

    assert path.endswith(".md")
    assert "/dev/" in path
    assert generated_at
    assert ingest == {"enabled": False, "ran": False}

    text = Path(path).read_text(encoding="utf-8")
    assert "# [Dev] Unit Test Note" in text
    assert "> Generated at:" in text
    assert "### Core" in text


def test_maybe_auto_ingest_reports_missing_dependency(monkeypatch, tmp_path):
    home = tmp_path / "home"
    knowledge_root = tmp_path / "knowledge-base"
    note_path = knowledge_root / "40_Agent_Notes" / "distilled-conversations" / "dev" / "note.md"
    note_path.parent.mkdir(parents=True)
    note_path.write_text("body", encoding="utf-8")
    knowledge_root.mkdir(exist_ok=True)
    home.mkdir()
    write_memory_config(home, [str(knowledge_root)])
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(save_note, "FRONTMATTER_SCRIPT", tmp_path / "missing-frontmatter.py")
    monkeypatch.setattr(save_note, "INDEXER_SCRIPT", tmp_path / "missing-indexer.py")

    result = save_note.maybe_auto_ingest(str(note_path))

    assert result["enabled"] is True
    assert result["ran"] is False
    assert result["reason"] == "missing_dependency"


def test_cli_json_print_json_returns_machine_readable_output(monkeypatch, tmp_path):
    home = tmp_path / "home"
    knowledge_root = tmp_path / "knowledge-base"
    knowledge_root.mkdir()
    home.mkdir()
    write_memory_config(home, [str(knowledge_root)])
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps({"title": "[Dev] CLI JSON", "content": "body"}, ensure_ascii=False),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env[save_note.AUTO_INGEST_ENV] = "false"

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json", str(payload_path), "--print-json"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout.strip())
    assert result["ok"] is True
    assert Path(result["path"]).exists()


def test_cli_invalid_json_returns_error(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ bad json }", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--json", str(bad_json)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "Invalid JSON payload" in (proc.stdout + proc.stderr)
