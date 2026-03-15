import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "core-skills" / "skill-security-audit" / "scripts" / "audit.py"

spec = importlib.util.spec_from_file_location("kitclaw_skill_security_audit", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load module spec for {SCRIPT_PATH}")
skill_security_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skill_security_audit)


def make_skill(skill_dir: Path, skill_md: str, script_body: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "main.py").write_text(script_body, encoding="utf-8")


def test_audit_single_skill_detects_hardcoded_secret(tmp_path):
    skill_dir = tmp_path / "unsafe-skill"
    make_skill(
        skill_dir,
        "---\nname: unsafe-skill\ndescription: local utility\n---\n",
        'API_KEY = "sk-123456789012345678901234"\n',
    )

    result = skill_security_audit.audit_single_skill(skill_dir)

    assert result["status"] == "CRITICAL"
    assert result["summary"]["critical"] == 1
    assert result["findings"][0]["dimension"] == "credential_leak"
    assert result["findings"][0]["severity"] == "critical"


def test_audit_single_skill_detects_undeclared_network_access(tmp_path):
    skill_dir = tmp_path / "network-skill"
    make_skill(
        skill_dir,
        "---\nname: network-skill\ndescription: local utility\n---\n",
        "import requests\nrequests.get('https://example.com')\n",
    )

    result = skill_security_audit.audit_single_skill(skill_dir)

    rule_ids = {finding["rule_id"] for finding in result["findings"]}
    assert "EXFIL-001" in rule_ids
    assert "NET-001" in rule_ids


def test_cli_json_output_reports_summary(tmp_path):
    skill_dir = tmp_path / "safe-skill"
    make_skill(
        skill_dir,
        "---\nname: safe-skill\ndescription: local utility\nio:\n  output:\n    - type: json_data\n---\n",
        "from pathlib import Path\nPath('out.json').write_text('{}', encoding='utf-8')\n",
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(skill_dir), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["global_summary"]["total_skills"] == 1
    assert payload["results"][0]["skill_name"] == "safe-skill"
