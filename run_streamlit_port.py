"""
Запуск Streamlit на порту из переменной PORT (для Railway и др.).
Использование: python run_streamlit_port.py
"""
import os
import subprocess
import sys

port = os.environ.get("PORT", "8501")
try:
    port = str(int(port))
except ValueError:
    port = "8501"

cmd = [
    sys.executable, "-m", "streamlit", "run", "app.py",
    "--server.port", port,
    "--server.address", "0.0.0.0",
    "--server.headless", "true",
]
sys.exit(subprocess.run(cmd).returncode)
