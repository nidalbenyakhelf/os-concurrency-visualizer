cat << 'EOF' > server.py
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from assistant.intent_parser import parse_command
from assistant.knowledge_base import answer_concept
from core.simulation import ProducerConsumerSimulation, SimulationSnapshot

UI_DIR = Path(__file__).resolve().parent / "ui"


class SimulationController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_state: Dict[str, Any] = {}
        self.sim = ProducerConsumerSimulation(
            capacity=5,
            num_producers=2,
            num_consumers=2,
            producer_delay=1.0,
            consumer_delay=1.2,
            on_update=self._on_snapshot,
        )
        self.sim.start()

    def _on_snapshot(self, snap: SimulationSnapshot) -> None:
        with self._lock:
            self._latest_state = {
                "tick": snap.tick,
                "buffer": snap.buffer,
                "capacity": snap.capacity,
                "mode": snap.mode.value,
                "workers": {
                    wid: {
                        "worker_id": w.worker_id,
                        "role": w.role,
                        "state": w.state.value,
                        "reason": w.reason,
                        "delay": w.delay,
                        "last_action": w.last_action,
                    }
                    for wid, w in snap.workers.items()
                },
                "logs": snap.logs,
            }

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._latest_state)

    def _current_delays(self) -> Dict[str, float]:
        state = self.get_state()
        workers = state.get("workers", {})
        delays: Dict[str, float] = {}
        for w in workers.values():
            role = w.get("role")
            if role and role not in delays:
                delays[role] = float(w.get("delay", 1.0))
        return delays

    def apply_control(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = str(payload.get("action", "")).upper()
        if action == "PLAY":
            self.sim.play()
        elif action == "PAUSE":
            self.sim.pause()
        elif action == "STEP":
            steps = int(payload.get("steps", 1))
            self.sim.step_forward(steps=steps)
        elif action == "SET_SPEED":
            role = str(payload.get("role", "")).upper()
            delay = float(payload.get("delay", 1.0))
            if role in ("PRODUCER", "CONSUMER"):
                self.sim.set_role_speed(role, delay)
        return self.get_state()

    def handle_chat(self, message: str) -> Dict[str, Any]:
        parsed = parse_command(message, current_delays=self._current_delays())
        applied_changes: Optional[Dict[str, Any]] = None

        if parsed.action_type == "PLAY":
            self.sim.play()
            reply = parsed.message
            applied_changes = {"mode": "PLAY"}
        elif parsed.action_type == "PAUSE":
            self.sim.pause()
            reply = parsed.message
            applied_changes = {"mode": "PAUSE"}
        elif parsed.action_type == "STEP":
            steps = int(parsed.payload.get("steps", 1))
            self.sim.step_forward(steps=steps)
            reply = parsed.message
            applied_changes = {"step": steps}
        elif parsed.action_type == "SET_SPEED":
            speeds = parsed.payload.get("speeds", {})
            for role, delay in speeds.items():
                self.sim.set_role_speed(role, float(delay))
            reply = parsed.message
            applied_changes = {"speeds": speeds}
        else:
            query = str(parsed.payload.get("query", message))
            reply = answer_concept(query)

        return {
            "reply": reply,
            "action_type": parsed.action_type,
            "applied_changes": applied_changes,
            "state": self.get_state(),
        }

    def shutdown(self) -> None:
        self.sim.stop()


def create_handler(controller: SimulationController):
    class VisualizerHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(UI_DIR), **kwargs)

        def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)

        def do_GET(self) -> None:
            parsed_url = urlparse(self.path)
            if parsed_url.path == "/api/state":
                self._send_json(200, controller.get_state())
                return
            if parsed_url.path == "/":
                self.path = "/index.html"
            super().do_GET()

        def do_POST(self) -> None:
            parsed_url = urlparse(self.path)
            try:
                payload = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json(400, {"error": "Invalid JSON body"})
                return

            if parsed_url.path == "/api/control":
                self._send_json(200, controller.apply_control(payload))
                return
            if parsed_url.path == "/api/chat":
                message = str(payload.get("message", "")).strip()
                if not message:
                    self._send_json(400, {"error": "Message is required"})
                    return
                self._send_json(200, controller.handle_chat(message))
                return

            self._send_json(404, {"error": "Endpoint not found"})

        def log_message(self, format: str, *args: Any) -> None:
            return

    return VisualizerHandler


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    controller = SimulationController()
    server = ThreadingHTTPServer((host, port), create_handler(controller))
    print(f"OS Concurrency Visualizer running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down simulation server...")
    finally:
        server.server_close()
        controller.shutdown()
