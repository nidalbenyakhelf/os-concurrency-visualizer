import os
import webbrowser
from server import run_server

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    if os.environ.get("OPEN_BROWSER", "1") == "1" and host in ("127.0.0.1", "localhost"):
        webbrowser.open(f"http://127.0.0.1:{port}")
    run_server(host=host, port=port)
