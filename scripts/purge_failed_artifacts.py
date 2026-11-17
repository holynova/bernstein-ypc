#!/usr/bin/env python3
"""
Purge failed studio artifacts from NotebookLM notebooks to prevent 100-artifact quota choking.
NEVER deletes completed/ready artifacts.
"""

import json
import subprocess
import time

STATE_FILE = "/Users/sym/code/bernstein-ypc/state/progress.json"
NLM_BIN = "/Users/sym/.local/bin/nlm"

def purge_notebook(nb_id: str, profile: str, label: str):
    print(f"\n=== Starting purge for {label} ({profile}, nb: {nb_id}) ===")
    total_deleted = 0
    while True:
        cmd = [NLM_BIN, "studio", "status", nb_id, "--profile", profile, "--json", "--limit", "100"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error fetching artifacts for {label}: {res.stderr}")
            break
        try:
            arts = json.loads(res.stdout)
        except Exception as e:
            print(f"JSON parse error for {label}: {e}")
            break

        failed = [
            a for a in arts 
            if str(a.get("status", "")).lower() in ("failed", "error", "4")
        ]
        if not failed:
            print(f"No more failed artifacts in {label}. (Total remaining artifacts: {len(arts)})")
            break

        print(f"Found batch of {len(failed)} failed artifacts in {label} to delete...")
        for a in failed:
            aid = a.get("artifact_id") or a.get("id")
            if not aid:
                continue
            del_cmd = [NLM_BIN, "studio", "delete", nb_id, aid, "-y", "--profile", profile]
            dres = subprocess.run(del_cmd, capture_output=True, text=True)
            if dres.returncode == 0:
                total_deleted += 1
            else:
                print(f"Failed to delete {aid}: {dres.stderr.strip()}")
            time.sleep(0.5)

    print(f"Finished purge for {label}: deleted {total_deleted} failed artifacts.")
    return total_deleted

def main():
    with open(STATE_FILE) as f:
        state = json.load(f)

    b1_id = state["notebooks"]["bucket_1"]["notebook_id"]
    b1_prof = state["notebooks"]["bucket_1"]["profile"]

    b2_id = state["notebooks"]["bucket_2"]["notebook_id"]
    b2_prof = state["notebooks"]["bucket_2"]["profile"]

    del2 = purge_notebook(b2_id, b2_prof, "bucket_2")
    del1 = purge_notebook(b1_id, b1_prof, "bucket_1")

    print(f"\nAll done! Total purged: {del1 + del2} failed artifacts.")

if __name__ == "__main__":
    main()
