"""Launcher fallback; only the existing verified-ownership helper may stop a process."""
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent / 'runtime'))
from slm.owned_ollama import OwnedOllama
from workflow.review_events import EventJournal

if __name__ == '__main__':
    journal = EventJournal(Path(sys.argv[2]), str(uuid4()))
    proof = OwnedOllama(Path(sys.argv[1]), journal=journal, endpoint='http://127.0.0.1:11434').stop()
    print(json.dumps(proof))
    raise SystemExit(0 if proof['status'] == 'owned_process_tree_terminated' else 2)
