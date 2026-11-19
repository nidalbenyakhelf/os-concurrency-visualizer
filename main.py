
import webbrowser
from server import run_server

if __name__ == "__main__":
    url = "http://127.0.0.1:8000"
    webbrowser.open(url)
    run_server(host="127.0.0.1", port=8000)
