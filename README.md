# OS Concurrency Visualizer

Interactive simulation tool in **Python** for multi-producer, multi-consumer synchronization using a bounded buffer and semaphores (`empty`, `full`, `mutex`), with `Play` / `Pause` / `Step Forward` controls, dynamic speed adjustments, and an OS concept & command assistant.

## Run Locally

```bash
python main.py
#### `main.py`
```bash
cat << 'EOF' > main.py
import webbrowser
from server import run_server

if __name__ == "__main__":
    url = "http://127.0.0.1:8000"
    webbrowser.open(url)
    run_server(host="127.0.0.1", port=8000)
