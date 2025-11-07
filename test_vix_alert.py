import json
import subprocess
import sys
from pathlib import Path


def test_script_runs_and_outputs_json():
    script = Path(__file__).parent / "vix_alert.py"
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode in (0, 2), f"Unexpected exit code: {proc.returncode}\nSTDERR: {proc.stderr}"
    # Validate JSON
    data = json.loads(proc.stdout.strip().splitlines()[-1])  # last line JSON
    for key in ("timestamp", "vix", "threshold", "exceeded"):
        assert key in data, f"Missing key {key} in payload {data}"
    assert isinstance(data["exceeded"], bool)
    assert isinstance(data["threshold"], (int, float)) and data["threshold"] == 35.0
