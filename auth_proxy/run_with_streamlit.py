"""
Запуск прокси и Streamlit одним процессом.
Использование: из корня репозитория:
  python auth_proxy/run_with_streamlit.py
Или из auth_proxy с заданием пути к app:
  STREAMLIT_APP=../app.py python run_with_streamlit.py
"""
import os
import subprocess
import sys
import time

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_py = os.path.join(root, "app.py")
    streamlit_app = os.environ.get("STREAMLIT_APP", app_py)
    if not os.path.isfile(streamlit_app):
        streamlit_app = "app.py"
    streamlit_port = os.environ.get("STREAMLIT_PORT", "8501")
    proxy_port = os.environ.get("PORT", "8000")
    os.environ["STREAMLIT_URL"] = os.environ.get("STREAMLIT_URL", f"http://127.0.0.1:{streamlit_port}")

    # Запуск Streamlit в фоне
    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run",
        streamlit_app,
        "--server.port", streamlit_port,
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
    ]
    proc = subprocess.Popen(streamlit_cmd, cwd=root, env=os.environ)
    try:
        time.sleep(2)
        if proc.poll() is not None:
            print("Streamlit failed to start")
            sys.exit(1)
        # Запуск прокси (блокирующий)
        sys.path.insert(0, os.path.dirname(__file__))
        from main import app
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=int(proxy_port))
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
