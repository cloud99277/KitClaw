import json
import subprocess
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_DIR / "scripts" / "runtime_doctor.py"

spec = spec_from_file_location("runtime_doctor", SCRIPT_PATH)
runtime_doctor = module_from_spec(spec)
sys.modules[spec.name] = runtime_doctor
spec.loader.exec_module(runtime_doctor)


def build_temp_runtime(tmp_path: Path) -> Path:
    skills_root = tmp_path / "ai-skills"
    memory_root = tmp_path / "ai-memory"
    codex_root = tmp_path / "codex"
    agents_root = tmp_path / "agents" / "skills"
    openclaw_root = tmp_path / "openclaw"
    l3_root = tmp_path / "knowledge"

    for path in [skills_root, memory_root, codex_root / "skills", agents_root, openclaw_root / "skills", l3_root]:
        path.mkdir(parents=True, exist_ok=True)

    (skills_root / ".logs").mkdir()

    (memory_root / "whiteboard.json").write_text(
        json.dumps({"schema_version": "1.0", "entries": []}),
        encoding="utf-8",
    )
    (memory_root / "config.json").write_text(
        json.dumps({"schema_version": "1.0", "l3_paths": [str(l3_root)]}),
        encoding="utf-8",
    )
    (codex_root / "config.toml").write_text(
        "\n".join(
            [
                "[shell_environment_policy.set]",
                'AI_AGENT_MODE = "1"',
                f'AI_SKILLS_DIR = "{skills_root}"',
                f'AI_MEMORY_DIR = "{memory_root}"',
            ]
        ),
        encoding="utf-8",
    )
    (codex_root / ".codex-global-state.json").write_text(
        json.dumps(
            {
                "runCodexInWindowsSubsystemForLinux": True,
                "electron-persisted-atom-state": {"runCodexInWindowsSubsystemForLinux": True},
            }
        ),
        encoding="utf-8",
    )
    (openclaw_root / "skills" / "shared").symlink_to(skills_root)

    curated = ["knowledge-search", "memory-manager", "l2-capture", "conversation-distiller", "skill-observability"]
    for name in curated:
        target = agents_root / name
        target.mkdir()
        (codex_root / "skills" / name).symlink_to(target)

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
            "l3_roots": [str(l3_root)],
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
            "shared_skill_link": str(openclaw_root / "skills" / "shared"),
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


class RuntimeDoctorTests(unittest.TestCase):
    def test_run_doctor_passes_on_valid_temp_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = build_temp_runtime(Path(temp_dir))
            report = runtime_doctor.run_doctor(manifest_path)
            self.assertEqual(report["summary"]["fail"], 0)
            statuses = {item["name"]: item["status"] for item in report["checks"]}
            self.assertEqual(statuses["codex_wsl_mode"], "PASS")
            self.assertEqual(statuses["openclaw_shared_link"], "PASS")

    def test_run_doctor_detects_missing_bridge_link(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest_path = build_temp_runtime(temp_path)
            broken_link = temp_path / "codex" / "skills" / "memory-manager"
            broken_link.unlink()
            report = runtime_doctor.run_doctor(manifest_path)
            statuses = {item["name"]: item["status"] for item in report["checks"]}
            self.assertEqual(statuses["codex_skill:memory-manager"], "FAIL")
            self.assertGreaterEqual(report["summary"]["fail"], 1)

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
            self.assertEqual(payload["summary"]["fail"], 0)
            self.assertTrue(any(item["name"] == "manifest" for item in payload["checks"]))


if __name__ == "__main__":
    unittest.main()
