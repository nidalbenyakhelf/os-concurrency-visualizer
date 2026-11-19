cat << 'EOF' > assistant/knowledge_base.py
from typing import Dict


CONCEPTS: Dict[str, str] = {
    "critical_section": (
        "Critical Section: The code segment where a thread accesses shared data "
        "(such as the bounded buffer). Only one thread should execute inside it at "
        "a time to prevent race conditions."
    ),
    "shared_resource": (
        "Shared Resource: Data or hardware accessed concurrently by multiple threads, "
        "such as the bounded buffer shared between producer and consumer threads."
    ),
    "semaphore": (
        "Semaphore: A synchronization primitive with an integer counter and two atomic "
        "operations (wait/acquire and signal/release). Here, `empty` tracks free slots, "
        "`full` tracks available items, and `mutex` enforces mutual exclusion."
    ),
    "race_condition": (
        "Race Condition: A flaw where system behavior depends on the timing or "
        "interleaving of concurrent threads, potentially corrupting shared state if "
        "synchronization is missing."
    ),
    "overflow_underflow": (
        "Buffer Overflow occurs when a producer tries to insert into a full buffer; "
        "Buffer Underflow occurs when a consumer tries to remove from an empty buffer. "
        "`empty` and `full` semaphores prevent both by blocking threads when needed."
    ),
    "thread_states": (
        "Thread States in this visualizer: RUNNING indicates active execution or "
        "progressing through steps, while BLOCKED indicates a thread waiting on a "
        "semaphore (`empty`, `full`) or `mutex`."
    ),
}


def answer_concept(query: str) -> str:
    q = query.lower().strip()

    if any(k in q for k in ("critical section", "critical", "قسم حرج", "منطقة حرجة")):
        return CONCEPTS["critical_section"]
    if any(k in q for k in ("shared", "resource", "buffer", "مورد مشترك", "مخزن")):
        return CONCEPTS["shared_resource"]
    if any(k in q for k in ("semaphore", "empty", "full", "mutex", "سيمافور", "قفل")):
        return CONCEPTS["semaphore"]
    if any(k in q for k in ("race", "تضارب", "سباق")):
        return CONCEPTS["race_condition"]
    if any(k in q for k in ("overflow", "underflow", "فيض", "نقص", "امتلاء", "فارغ")):
        return CONCEPTS["overflow_underflow"]
    if any(k in q for k in ("blocked", "running", "state", "حالة", "محجوب", "يعمل")):
        return CONCEPTS["thread_states"]

    return (
        "Ask me about: critical section, shared resource, semaphore (empty/full/mutex), "
        "race condition, buffer overflow/underflow, or thread states (RUNNING/BLOCKED), "
        "or give a command like 'slow down producers and speed up consumers'."
    )
