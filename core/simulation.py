from dataclasses import dataclass, field
from enum import Enum
import threading
import time
from typing import Any, Callable, Dict, List, Optional


class SimulationMode(str, Enum):
    PLAY = "PLAY"
    PAUSE = "PAUSE"
    STEP = "STEP"


class ThreadState(str, Enum):
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"


@dataclass
class WorkerStatus:
    worker_id: str
    role: str  # "PRODUCER" or "CONSUMER"
    state: ThreadState = ThreadState.RUNNING
    reason: str = "Idle"
    delay: float = 1.0
    last_action: str = "Initialized"


@dataclass
class SimulationSnapshot:
    tick: int
    buffer: List[Any]
    capacity: int
    mode: SimulationMode
    workers: Dict[str, WorkerStatus]
    logs: List[str] = field(default_factory=list)


class ProducerConsumerSimulation:
    def __init__(
        self,
        capacity: int = 5,
        num_producers: int = 2,
        num_consumers: int = 2,
        producer_delay: float = 1.0,
        consumer_delay: float = 1.2,
        on_update: Optional[Callable[[SimulationSnapshot], None]] = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError("Buffer capacity must be greater than 0")

        self.capacity = capacity
        self.buffer: List[Any] = []
        self._item_counter = 0
        self._tick = 0

        # Semaphores and mutex for bounded buffer synchronization
        self.empty = threading.Semaphore(capacity)
        self.full = threading.Semaphore(0)
        self.mutex = threading.Lock()

        # Execution control primitives
        self._mode = SimulationMode.PAUSE
        self._mode_condition = threading.Condition()
        self._step_budget = 0
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._on_update = on_update

        self._logs: List[str] = []
        self._workers: Dict[str, WorkerStatus] = {}
        self._threads: List[threading.Thread] = []

        for i in range(1, num_producers + 1):
            wid = f"P{i}"
            self._workers[wid] = WorkerStatus(
                worker_id=wid,
                role="PRODUCER",
                delay=producer_delay,
                last_action="Ready to produce",
            )

        for i in range(1, num_consumers + 1):
            wid = f"C{i}"
            self._workers[wid] = WorkerStatus(
                worker_id=wid,
                role="CONSUMER",
                delay=consumer_delay,
                last_action="Ready to consume",
            )

    def start(self) -> None:
        if self._threads:
            return
        for wid, status in self._workers.items():
            target = (
                self._producer_loop if status.role == "PRODUCER" else self._consumer_loop
            )
            t = threading.Thread(target=target, args=(wid,), name=wid, daemon=True)
            self._threads.append(t)
            t.start()
        self._log("Simulation threads started in PAUSE mode.")
        self._emit_snapshot()

    def stop(self) -> None:
        self._stop_event.set()
        with self._mode_condition:
            self._mode_condition.notify_all()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()

    def play(self) -> None:
        with self._mode_condition:
            self._mode = SimulationMode.PLAY
            self._step_budget = 0
            self._log("Mode set to PLAY.")
            self._mode_condition.notify_all()
        self._emit_snapshot()

    def pause(self) -> None:
        with self._mode_condition:
            self._mode = SimulationMode.PAUSE
            self._step_budget = 0
            self._log("Mode set to PAUSE.")
            self._mode_condition.notify_all()
        self._emit_snapshot()

    def step_forward(self, steps: int = 1) -> None:
        with self._mode_condition:
            self._mode = SimulationMode.STEP
            self._step_budget += max(1, steps)
            self._log(f"Stepping forward by {max(1, steps)} action(s).")
            self._mode_condition.notify_all()

    def set_role_speed(self, role: str, delay: float) -> None:
        role_upper = role.upper()
        safe_delay = max(0.1, float(delay))
        with self._state_lock:
            for status in self._workers.values():
                if status.role == role_upper:
                    status.delay = safe_delay
        self._log(f"{role_upper} delay updated to {safe_delay:.2f}s.")
        self._emit_snapshot()

    def _acquire_step_permission(self) -> bool:
        with self._mode_condition:
            while not self._stop_event.is_set():
                if self._mode == SimulationMode.PLAY:
                    return True
                if self._mode == SimulationMode.STEP and self._step_budget > 0:
                    self._step_budget -= 1
                    if self._step_budget == 0:
                        self._mode = SimulationMode.PAUSE
                    return True
                self._mode_condition.wait(timeout=0.1)
        return False

    def _set_worker_state(
        self, wid: str, state: ThreadState, reason: str, action: Optional[str] = None
    ) -> None:
        with self._state_lock:
            ws = self._workers[wid]
            ws.state = state
            ws.reason = reason
            if action is not None:
                ws.last_action = action
        self._emit_snapshot()

    def _get_worker_delay(self, wid: str) -> float:
        with self._state_lock:
            return self._workers[wid].delay

    def _log(self, message: str) -> None:
        with self._state_lock:
            self._tick += 1
            self._logs.append(f"[T{self._tick:04d}] {message}")
            self._logs = self._logs[-100:]

    def _emit_snapshot(self) -> None:
        if not self._on_update:
            return
        with self._state_lock:
            snap = SimulationSnapshot(
                tick=self._tick,
                buffer=list(self.buffer),
                capacity=self.capacity,
                mode=self._mode,
                workers={
                    k: WorkerStatus(
                        worker_id=v.worker_id,
                        role=v.role,
                        state=v.state,
                        reason=v.reason,
                        delay=v.delay,
                        last_action=v.last_action,
                    )
                    for k, v in self._workers.items()
                },
                logs=list(self._logs),
            )
        self._on_update(snap)

    def _producer_loop(self, wid: str) -> None:
        while not self._stop_event.is_set():
            if not self._acquire_step_permission():
                break

            # Wait if buffer is full (empty semaphore == 0)
            self._set_worker_state(
                wid,
                ThreadState.BLOCKED,
                "Waiting for empty slot (Buffer Full)",
                "Wait empty semaphore",
            )
            self.empty.acquire()
            if self._stop_event.is_set():
                self.empty.release()
                break

            # Enter critical section to append item safely
            self._set_worker_state(
                wid,
                ThreadState.BLOCKED,
                "Waiting for buffer mutex",
                "Acquire mutex",
            )
            with self.mutex:
                self._set_worker_state(
                    wid,
                    ThreadState.RUNNING,
                    "Inserting item into buffer",
                    "Produce item",
                )
                self._item_counter += 1
                item = f"{wid}-Item#{self._item_counter}"
                self.buffer.append(item)
                self._log(f"{wid} produced {item} | Buffer size: {len(self.buffer)}/{self.capacity}")
                self._emit_snapshot()
                time.sleep(self._get_worker_delay(wid))

            self.full.release()
            self._set_worker_state(
                wid,
                ThreadState.RUNNING,
                "Signaled full semaphore",
                f"Produced {item}",
            )

    def _consumer_loop(self, wid: str) -> None:
        while not self._stop_event.is_set():
            if not self._acquire_step_permission():
                break

            # Wait if buffer is empty (full semaphore == 0)
            self._set_worker_state(
                wid,
                ThreadState.BLOCKED,
                "Waiting for available item (Buffer Empty)",
                "Wait full semaphore",
            )
            self.full.acquire()
            if self._stop_event.is_set():
                self.full.release()
                break

            # Enter critical section to remove item safely
            self._set_worker_state(
                wid,
                ThreadState.BLOCKED,
                "Waiting for buffer mutex",
                "Acquire mutex",
            )
            with self.mutex:
                self._set_worker_state(
                    wid,
                    ThreadState.RUNNING,
                    "Removing item from buffer",
                    "Consume item",
                )
                item = self.buffer.pop(0)
                self._log(f"{wid} consumed {item} | Buffer size: {len(self.buffer)}/{self.capacity}")
                self._emit_snapshot()
                time.sleep(self._get_worker_delay(wid))

            self.empty.release()
            self._set_worker_state(
                wid,
                ThreadState.RUNNING,
                "Signaled empty semaphore",
                f"Consumed {item}",
            )
