#!/usr/bin/env python3
import json
import subprocess
import tempfile
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(["python", str(ROOT / "tools" / "campaignctl.py"), "--project", str(ROOT), *args], capture_output=True, text=True)


def main():
    check = run("check")
    assert check.returncode == 0, check.stdout + check.stderr
    data = json.loads(check.stdout)
    assert data["status"] == "ok"

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "project"
        shutil.copytree(ROOT, tmp)
        state = json.loads((tmp / "state" / "_campaign-state.json").read_text(encoding="utf-8"))
        tx = {
            "expected_state_revision": state["state_revision"],
            "event": {"id": "TEST-001", "summary": "Тестовая смена времени.", "visibility": "party"},
            "operations": [{"type": "set_world_field", "field": "time_label", "value": "ночь"}],
        }
        tx_path = tmp / "transactions" / "test.json"
        tx_path.parent.mkdir(parents=True, exist_ok=True)
        tx_path.write_text(json.dumps(tx, ensure_ascii=False, indent=2), encoding="utf-8")

        preview = subprocess.run(["python", str(tmp / "tools" / "campaignctl.py"), "--project", str(tmp), "preview", "--transaction", str(tx_path)], capture_output=True, text=True)
        assert preview.returncode == 0, preview.stdout + preview.stderr
        assert json.loads((tmp / "state" / "_campaign-state.json").read_text(encoding="utf-8"))["state_revision"] == state["state_revision"]

        commit = subprocess.run(["python", str(tmp / "tools" / "campaignctl.py"), "--project", str(tmp), "commit", "--transaction", str(tx_path)], capture_output=True, text=True)
        assert commit.returncode == 0, commit.stdout + commit.stderr
        new_state = json.loads((tmp / "state" / "_campaign-state.json").read_text(encoding="utf-8"))
        assert new_state["state_revision"] == state["state_revision"] + 1
        assert new_state["world"]["time_label"] == "ночь"

        duplicate = subprocess.run(["python", str(tmp / "tools" / "campaignctl.py"), "--project", str(tmp), "commit", "--transaction", str(tx_path)], capture_output=True, text=True)
        assert duplicate.returncode == 0
        assert json.loads(duplicate.stdout)["status"] == "already_applied"
        tx["event"]["id"] = "TEST-STALE-NEW-EVENT"
        tx_path.write_text(json.dumps(tx), encoding="utf-8")
        stale = subprocess.run(["python", str(tmp / "tools" / "campaignctl.py"), "--project", str(tmp), "commit", "--transaction", str(tx_path)], capture_output=True, text=True)
        assert stale.returncode != 0

    print("MVP tests: OK")


if __name__ == "__main__":
    main()
