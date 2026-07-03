# run_all.py
import subprocess
import time
import sys
from pathlib import Path

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"

processes: list[subprocess.Popen] = []


def shutdown():
    print("\nShutting down servers...")
    for p in processes:
        p.terminate()
    for p in processes:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    print("Servers stopped cleanly.")


try:
    print("Starting FastAPI API Server (port 8000) and React Web App (port 5173)...")
    api_process = subprocess.Popen(
        ["uv", "run", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=str(ROOT),
    )
    processes.append(api_process)

    # Give the API a moment to come up before the web proxy needs it
    time.sleep(2)

    web_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(WEB_DIR),
    )
    processes.append(web_process)

    print("\n  FastAPI:  http://localhost:8000  (API — /api/*)")
    print("  Web app:  http://localhost:5173  (React UI, proxies /api → :8000)")
    print("  Press CTRL+C to stop both.\n")

    # Keep the orchestrator script alive
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    shutdown()
except Exception:
    shutdown()
    raise
