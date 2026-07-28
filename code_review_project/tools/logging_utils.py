import json
from datetime import datetime
import os

# FIX: this previously pointed at "injection_log.jsonl" (appended one JSON
# object per line), but every downstream consumer (verifier, scorer,
# ground_truth/injection_log.json shipped in the branch) expects a single
# JSON array at "injection_log.json". Point the logger at the real file so
# there's one source of truth instead of two log files quietly diverging.
LOG_FILE = "ground_truth/injection_log.json"


def _read_existing_log():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return []
    return json.loads(content)


def log_injection(file_path, function_name, line_num, bug_type, description,
                  original_code, mutated_code):
    log_entry = {
        "file": file_path,
        "function": function_name,
        "line": line_num,
        "bug_type": bug_type,
        "description": description,
        "original_code": original_code,
        "mutated_code": mutated_code,
        "injection_metadata": {
            "timestamp": datetime.now().isoformat(),
            "mutator_version": "v1.1",
            "random_seed": 42
        }
    }
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    entries = _read_existing_log()
    entries.append(log_entry)
    with open(LOG_FILE, "w", encoding='utf-8') as f:
        json.dump(entries, f, indent=2)
    return log_entry


def clear_log():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
        print("Log cleared")
