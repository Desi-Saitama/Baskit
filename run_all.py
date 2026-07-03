# run_all.py
import subprocess
import time
import sys

try:
    print("Starting API Server and Streamlit...")
    api_process = subprocess.Popen(["uv", "run", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])
    streamlit_process = subprocess.Popen(["uv", "run", "streamlit", "run", "app.py"])
    
    # Keep the orchestrator script alive
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down both servers...")
    api_process.terminate()
    streamlit_process.terminate()
    api_process.wait()
    streamlit_process.wait()
    print("Both servers stopped cleanly.")
