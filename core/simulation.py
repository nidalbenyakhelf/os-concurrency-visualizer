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
    role: str
    state: ThreadState = ThreadState.RUNNING
    reason: str = "Ready"
    delay: float = 1.0
    last_action: str = "Initialized"


@dataclass
class SimulationSnapshot:
    tick: int
    buffer: List[Any]
    capacity: int
    mode: SimulationMode
    empty_count: int
    full_count: int
    mutex_locked: bool
    mutex_owner: Optional[str]
    workers: Dict[str, WorkerStatus]
    logs: List[str] = field(default_factory=list)
    last_event: Optional[Dict[str, Any]] = None


class ProducerConsumerSimulation:
    def __init__(
        self,
        capacity: int = 6,
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

        # Mirrored counters for transparent OS state inspection
        self._empty_value = capacity
        self._full_value = 0
        self._mutex_owner: Optional[str] = None
        self._last_event: Optional[Dict[str, Any]] = None

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
        self._record_log("Simulation initialized in PAUSE mode.", {"type": "INIT"})
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
            self._mode_condition.notify_all()
        self._record_log("Simulation mode switched to PLAY.", {"type": "MODE", "mode": "PLAY"})
        self._emit_snapshot()

    def pause(self) -> None:
        with self._mode_condition:
            self._mode = SimulationMode.PAUSE
            self._step_budget = 0
            self._mode_condition.notify_all()
        self._record_log("Simulation mode switched to PAUSE.", {"type": "MODE", "mode": "PAUSE"})
        self._emit_snapshot()

    def step_forward(self, steps: int = 1) -> None:
        count = max(1, steps)
        with self._mode_condition:
            self._mode = SimulationMode.STEP
            self._step_budget += count
            self._mode_condition.notify_all()
        self._record_log(f"Step Forward requested ({count} step).", {"type": "STEP", "steps": count})
        self._emit_snapshot()

    def set_role_speed(self, role: str, delay: float) -> None:
        role_upper = role.upper()
        safe_delay = max(0.15, min(5.0, float(delay)))
        with self._state_lock:
            for status in self._workers.values():
                if status.role == role_upper:
                    status.delay = safe_delay
        self._record_log(
            f"{role_upper} delay set to {safe_delay:.2f}s.",
            {"type": "SPEED", "role": role_upper, "delay": safe_delay},
        )
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

    def _record_log(self, message: str, event: Optional[Dict[str, Any]] = None) -> None:
        with self._state_lock:
            self._tick += 1
            self._logs.append(f"[T{self._tick:04d}] {message}")
            self._logs = self._logs[-120:]
            if event is not None:
                self._last_event = {**event, "tick": self._tick}

    def _emit_snapshot(self) -> None:
        if not self._on_update:
            return
        with self._state_lock:
            snap = SimulationSnapshot(
                tick=self._tick,
                buffer=list(self.buffer),
                capacity=self.capacity,
                mode=self._mode,
                empty_count=self._empty_value,
                full_count=self._full_value,
                mutex_locked=self._mutex_owner is not None,
                mutex_owner=self._mutex_owner,
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
                last_event=dict(self._last_event) if self._last_event else None,
            )
        self._on_update(snap)

    def _producer_loop(self, wid: str) -> None:
        while not self._stop_event.is_set():
            if not self._acquire_step_permission():
                break

            # 1) Wait on `empty` semaphore to prevent Buffer Overflow
            self._set_worker_state(
                wid,
                ThreadState.BLOCKED,
                "Blocked on wait(empty): buffer is full (prevents Overflow)",
                "wait(empty)",
            )
            self.empty.acquire()
            if self._stop_event.is_set():
                self.empty.release()
                break

            with self._state_lock:
                self._empty_value = max(0, self._empty_value - 1)

            # 2) Enter Critical Section via `mutex` to prevent Race Condition
            self._set_worker_state(
                wid,
                ThreadState.BLOCKED,
                "Blocked on wait(mutex): another thread holds critical section",
                "wait(mutex)",
            )
            with self.mutex:
                with self._state_lock:
                    self._mutex_owner = wid
                self._set_worker_state(
                    wid,
                    ThreadState.RUNNING,
                    "Inside Critical Section: writing item to bounded buffer",
                    "Produce -> Buffer",
                )
                with self._state_lock:
                    self._item_counter += 1
                    item = f"{wid}#{self._item_counter}"
                    self.buffer.append(item)
                self._record_log(
                    f"{wid} inserted {item} into Critical Section ({len(self.buffer)}/{self.capacity})",
                    {"type": "PRODUCE", "worker": wid, "item": item, "index": len(self.buffer) - 1},
                )
                self._emit_snapshot()
                time.sleep(self._get_worker_delay(wid))
                with self._state_lock:
                    self._mutex_owner = None

            # 3) Signal `full` semaphore that a new item is ready
            self.full.release()
            with self._state_lock:
                self._full_value = min(self.capacity, self._full_value + 1)
            self._set_worker_state(
                wid,
                ThreadState.RUNNING,
                "Executed signal(full): item available for consumers",
                "signal(full)",
            )

    def _consumer_loop(self, wid: str) -> None:
        while not self._stop_event.is_set():
            if not self._acquire_step_permission():
                break

            # 1) Wait on `full` semaphore to prevent Buffer Underflow
            self._set_worker_state(
                wid,
                ThreadState.BLOCKED,
                "Blocked on wait(full): buffer is empty (prevents Underflow)",
                "wait(full)",
            )
            self.full.acquire()
            if self._stop_event.is_set():
                self.full.release()
                break

            with self._state_lock:
                self._full_value = max(0, self._full_value - 1)

            # 2) Enter Critical Section via `mutex` to consume item safely
            self._set_worker_state(
                wid,
                ThreadState.BLOCKED,
                "Blocked on wait(mutex): waiting for exclusive buffer access",
                "wait(mutex)",
            )
            with self.mutex:
                with self._state_lock:
                    self._mutex_owner = wid
                self._set_worker_state(
                    wid,
                    ThreadState.RUNNING,
                    "Inside Critical Section: consuming item from bounded buffer",
                    "Consume <- Buffer",
                )
                with self._state_lock:
                    item = self.buffer.pop(0)
                self._record_log(
                    f"{wid} consumed {item} from Critical Section ({len(self.buffer)}/{self.capacity})",
                    {"type": "CONSUME", "worker": wid, "item": item},
                )
                self._emit_snapshot()
                time.sleep(self._get_worker_delay(wid))
                with self._state_lock:
                    self._mutex_owner = None

            # 3) Signal `empty` semaphore that a slot is now free
            self.empty.release()
            with self._state_lock:
                self._empty_value = min(self.capacity, self._empty_value + 1)
            self._set_worker_state(
                wid,
                ThreadState.RUNNING,
                "Executed signal(empty): free slot returned to buffer",
                "signal(empty)",
            )
