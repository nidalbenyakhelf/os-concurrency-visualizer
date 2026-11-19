cat << 'EOF' > assistant/intent_parser.py
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ParsedAction:
    action_type: str  # "SET_SPEED", "PLAY", "PAUSE", "STEP", "EXPLAIN"
    payload: Dict[str, Any]
    message: str


def _detect_roles(text: str) -> List[str]:
    roles: List[str] = []
    if any(w in text for w in ("producer", "producers", "منتج", "المنتجين", "المنتجون")):
        roles.append("PRODUCER")
    if any(w in text for w in ("consumer", "consumers", "مستهلك", "المستهلكين", "المستهلكون")):
        roles.append("CONSUMER")
    if not roles and any(w in text for w in ("all", "both", "الكل", "الجميع")):
        roles = ["PRODUCER", "CONSUMER"]
    return roles


def parse_command(text: str, current_delays: Optional[Dict[str, float]] = None) -> ParsedAction:
    cleaned = text.strip()
    lower = cleaned.lower()
    delays = current_delays or {"PRODUCER": 1.0, "CONSUMER": 1.2}

    # Playback controls
    if any(w in lower for w in ("pause", "stop simulation", "إيقاف مؤقت", "أوقف", "توقف")):
        return ParsedAction("PAUSE", {}, "Pausing simulation.")

    if any(w in lower for w in ("resume", "start", "play", "تشغيل", "استمر", "شغل")):
        if "step" not in lower and "خطوة" not in lower:
            return ParsedAction("PLAY", {}, "Resuming simulation playback.")

    if any(w in lower for w in ("step", "خطوة", "تقدم")):
        return ParsedAction("STEP", {"steps": 1}, "Advancing simulation by one step.")

    # Speed adjustments ("slow down", "speed up", "slower", "faster", "أبطئ", "سرّع")
    is_slower = any(
        w in lower
        for w in ("slow down", "slower", "decrease speed", "أبطئ", "ابطئ", "بطئ", "خفف السرعة")
    )
    is_faster = any(
        w in lower
        for w in ("speed up", "faster", "increase speed", "سرع", "سرّع", "زد السرعة", "أسرع")
    )

    if is_slower or is_faster:
        roles = _detect_roles(lower)
        if not roles:
            roles = ["PRODUCER", "CONSUMER"]

        updates: Dict[str, float] = {}
        for role in roles:
            base = delays.get(role, 1.0)
            # Increasing delay = slower thread; decreasing delay = faster thread
            factor = 1.5 if is_slower else 0.65
            updates[role] = round(max(0.15, min(5.0, base * factor)), 2)

        return ParsedAction(
            "SET_SPEED",
            {"speeds": updates},
            f"Updated delays: {updates}",
        )

    return ParsedAction("EXPLAIN", {"query": cleaned}, "")
