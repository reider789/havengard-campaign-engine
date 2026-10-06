#!/usr/bin/env python3
"""Apply queued files in revision order. Publishing the resulting Git commit is separate."""
import argparse
from pathlib import Path

from campaignctl import cmd_commit, read_json, CampaignError
from campaign_model import integer


def apply_pending(project: Path) -> int:
    pending = [(read_json(path), path) for path in (project / "transactions/live").glob("*.json")]
    if any(not integer(tx.get("expected_state_revision")) for tx, _ in pending):
        raise CampaignError("Каждая транзакция требует целую expected_state_revision")
    pending.sort(key=lambda item: (item[0]["expected_state_revision"], item[1].name))
    for _, path in pending:
        cmd_commit(project, path)
        path.unlink()  # cmd_commit has persisted both the receipt and immutable archive.
    return len(pending)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=".")
    args = parser.parse_args()
    print(f"Applied {apply_pending(Path(args.project).resolve())} queued transaction(s).")
