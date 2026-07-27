import json
from datetime import datetime
import os

LOG_FILE = "ground_truth/injection_log.jsonl"

def log_injection(file_path, function_name, line_num, bug_type, description, 
                  original_code, mutated_code):
    """Append one injection event to the log file."""
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
            "mutator_version": "v1.0",
            "random_seed": 42
        }
    }
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding='utf-8') as f:
        f.write(json.dumps(log_entry) + "\n")
    return log_entry

def clear_log():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
        print("Log cleared")