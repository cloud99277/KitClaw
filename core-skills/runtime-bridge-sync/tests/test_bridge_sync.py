import json
import subprocess
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_DIR / "scripts" / "bridge_sync.py"

spec = spec_from_file_location("bridge_sync", SCRIPT_PATH)
bridge_sync = module_from_spec(spec)
sys.modules[spec.name] = bridge_sync
spec.loader.exec_module(bridge_sync)


def build_temp_runtime(tmp_path: Path) -> Path:
    skills_root = tmp_path / "ai-skills"
    memory_root = tmp_path / "ai-memory"
    codex_root = tmp_path / "codex"
    agents_root = tmp_path / "agents" / "skills"

    for path in [skills_root, memory_root, codex_root / "skills", agents_root]:
        path.mkdir(parents=True, exist_ok=True)

    curated = ["knowledge-search", "memory-manager", "l2-capture", "conversation-distiller", "skill-observability"]
    for name in curated:
        target = agents_root / name
        target.mkdir()

    manifest = {
        "schema_version": "1.0",
        "runtime_name": "kitclaw-shared-runtime",
        "source_of_truth": "wsl",
        "canonical": {
            "skills_root": str(skills_root),
            "memory_root": str(memory_root),
            "whiteboard_path": str(memory_root / "whiteboard.json"),
            "memory_config_path": str(memory_root / "config.json"),
            "observability_log_path": str(skills_root / ".logs" / "executions.jsonl"),
            "l3_roots": [],
        },
        "windows": {
            "codex_config_path": str(codex_root / "config.toml"),
            "codex_global_state_path": str(codex_root / ".codex-global-state.json"),
            "codex_skill_root": str(codex_root / "skills"),
            "agents_skill_root": str(agents_root),
            "environment": {
                "AI_SKILLS_DIR": str(skills_root),
                "AI_MEMORY_DIR": str(memory_root),
            },
        },
        "openclaw": {
            "shared_skill_link": str(tmp_path / "openclaw" / "skills" / "shared"),
            "shared_skill_target": str(skills_root),
        },
        "bridge": {
            "mode": "curated-links",
            "curated_codex_skills": [
                {
                    "name": name,
                    "codex_link": str(codex_root / "skills" / name),
                    "target": str(agents_root / name),
                }
                for name in curated
            ],
        },
    }

    manifest_path = tmp_path / "runtime-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


class RuntimeBridgeSyncTests(unittest.TestCase):
    def test_dry_run_reports_create_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = build_temp_runtime(Path(temp_dir))
            report = bridge_sync.sync_bridge(manifest_path, apply_changes=False)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["summary"]["created"], 5)
            self.assertEqual(report["summary"]["updated"], 0)
            self.assertEqual(report["summary"]["noop"], 0)

    def test_apply_creates_symlinks_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest_path = build_temp_runtime(temp_path)

            first = bridge_sync.sync_bridge(manifest_path, apply_changes=True)
            self.assertEqual(first["status"], "ok")
            self.assertEqual(first["summary"]["created"], 5)

            second = bridge_sync.sync_bridge(manifest_path, apply_changes=True)
            self.assertEqual(second["status"], "ok")
            self.assertEqual(second["summary"]["noop"], 5)

            codex_skill_root = temp_path / "codex" / "skills"
            for name in ["knowledge-search", "memory-manager", "l2-capture", "conversation-distiller", "skill-observability"]:
                link = codex_skill_root / name
                self.assertTrue(link.is_symlink())
                self.assertTrue(link.resolve().exists())

    def test_cli_json_output_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = build_temp_runtime(Path(temp_dir))
            proc = subprocess.run(
                ["python3", str(SCRIPT_PATH), "--manifest", str(manifest_path), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["summary"]["created"], 5)


if __name__ == "__main__":
    unittest.main()
