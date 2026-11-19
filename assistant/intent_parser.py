from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ParsedAction:
    action_type: str
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

    if any(w in lower for w in ("pause", "إيقاف مؤقت", "أوقف", "توقف")):
        return ParsedAction("PAUSE", {}, "تم إيقاف المحاكاة مؤقتاً (`PAUSE`). يمكنك الضغط على `Step Forward` أو `Play` في أي وقت.")

    if any(w in lower for w in ("resume", "start", "play", "تشغيل", "استمر", "شغّل", "شغل")):
        if "step" not in lower and "خطوة" not in lower:
            return ParsedAction("PLAY", {}, "تم تشغيل المحاكاة (`PLAY`). راقب حركة العناصر وحالات `RUNNING` و`BLOCKED`.")

    if any(w in lower for w in ("step", "خطوة", "تقدم")):
        return ParsedAction("STEP", {"steps": 1}, "تم تنفيذ خطوة واحدة (`STEP FORWARD`).")

    is_slower = any(
        w in lower
        for w in ("slow down", "slower", "decrease speed", "أبطئ", "ابطئ", "بطئ", "خفف السرعة", "أبطأ")
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
        role_names_ar = {"PRODUCER": "المنتجين", "CONSUMER": "المستهلكين"}
        parts: List[str] = []

        for role in roles:
            base = delays.get(role, 1.0)
            factor = 1.5 if is_slower else 0.65
            new_delay = round(max(0.15, min(5.0, base * factor)), 2)
            updates[role] = new_delay
            verb = "إبطاء" if is_slower else "تسريع"
            parts.append(f"{verb} {role_names_ar.get(role, role)} إلى تأخير `{new_delay:.2f}s`")

        return ParsedAction(
            "SET_SPEED",
            {"speeds": updates},
            "تم تحديث السرعات: " + " و".join(parts) + ".",
        )

    return ParsedAction("EXPLAIN", {"query": cleaned}, "")
