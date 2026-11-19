from typing import Any, Dict, List, Optional


CONCEPT_DETAILS: Dict[str, Dict[str, str]] = {
    "critical_section": {
        "title": "القسم الحرج (Critical Section)",
        "body": (
            "هو مقطع الكود الذي يقرأ أو يعدّل مورداً مشتركاً (هنا مصفوفة المخزن المحدود `buffer`). "
            "إذا دخل أكثر من خيط في اللحظة نفسها دون تنسيق قد يحدث تلف للبيانات أو تضارب في المؤشرات."
        ),
        "example": "إضافة عنصر `self.buffer.append(item)` أو سحبه `self.buffer.pop(0)` يجب أن تكون محمية بـ `mutex`.",
    },
    "semaphore": {
        "title": "السيمافور و Mutex (Semaphores & Mutual Exclusion)",
        "body": (
            "نستخدم هنا ثلاثة عناصر مزامنة:\n"
            "• `empty`: عدّاد يبدأ بسعة المخزن (`capacity`) ويمنع المنتِج من الكتابة عندما يمتلئ المخزن (`Buffer Overflow`).\n"
            "• `full`: عدّاد يبدأ بـ `0` ويمنع المستهلِك من السحب عندما يكون المخزن فارغاً (`Buffer Underflow`).\n"
            "• `mutex`: قفل ثنائي يضمن دخول خيط واحد فقط إلى القسم الحرج في كل مرة (`Race Condition`)."
        ),
        "example": "المنتِج ينفّذ `wait(empty)` ثم `wait(mutex)` ثم يُعدّل المخزن ثم `signal(mutex)` ثم `signal(full)`.",
    },
    "race_condition": {
        "title": "حالة السباق (Race Condition)",
        "body": (
            "تحدث عندما تعتمد نتيجة التنفيذ على توقيت تبديل الخيوط (`Thread Scheduling`) غير المتوقع. "
            "بدون قفل `mutex` قد يتداخل منتِجان أو مستهلِكان في تعديل المخزن والعدّادات في الوقت نفسه."
        ),
        "example": "خيطان يقرآن حجم المخزن معاً في اللحظة ذاتها ثم يكتبان في الخانة نفسها.",
    },
    "overflow_underflow": {
        "title": "الفيض والنقص (Buffer Overflow & Underflow)",
        "body": (
            "• **Overflow:** محاولة وضع عنصر جديد في مخزن ممتلئ بالكامل؛ يمنعها `wait(empty)` بحجب المنتِج (`BLOCKED`).\n"
            "• **Underflow:** محاولة سحب عنصر من مخزن فارغ؛ يمنعها `wait(full)` بحجب المستهلِك (`BLOCKED`)."
        ),
        "example": "عندما يصل المخزن إلى `6/6`، يصبح `empty = 0` فينتظر المنتِج حتى يستهلك مستهلِك عنصراً ويُطلق `signal(empty)`.",
    },
    "states": {
        "title": "حالات الخيوط (RUNNING مقابل BLOCKED)",
        "body": (
            "• **RUNNING:** الخيط يملك وقت المعالج وينفّذ خطواته أو يعمل داخل القسم الحرج.\n"
            "• **BLOCKED:** الخيط متوقف مؤقتاً بانتظار شرط أو مورد (`empty == 0`، `full == 0`، أو `mutex` مشغول)، ولا يستهلك دورة معالجة عبثاً."
        ),
        "example": "إذا كان المستهلِكون أبطأ بكثير من المنتجين، سيمتلئ المخزن ثم تتحول خيوط المنتجين إلى `BLOCKED` تلقائياً.",
    },
    "deadlock_order": {
        "title": "لماذا يهم ترتيب `wait` و `signal`؟",
        "body": (
            "في المنتِج، يجب أن يأتي `wait(empty)` قبل `wait(mutex)`. لو أخذ الخيط `mutex` أولاً ثم وجد المخزن ممتلئاً ونام منتظراً `empty`، "
            "فقد يمنع الآخرين أو يبطئ التقدم بشكل خطير. وكذلك `signal(full)` يجب أن يُنفّذ بعد تحديث المخزن داخل `mutex`."
        ),
        "example": "دائماً: قيد السعة (`empty`/`full`) أولاً، ثم الاستبعاد المتبادل (`mutex`) حول الوصول الفعلي للمخزن.",
    },
}


def _summarize_live_state(state: Optional[Dict[str, Any]]) -> str:
    if not state or not state.get("workers"):
        return ""
    buf = state.get("buffer", [])
    cap = state.get("capacity", 0)
    mode = state.get("mode", "PAUSE")
    empty_c = state.get("empty_count", 0)
    full_c = state.get("full_count", 0)
    mutex_owner = state.get("mutex_owner") or "متاح (Free)"

    blocked = [
        f"{wid} ({w.get('reason')})"
        for wid, w in state["workers"].items()
        if w.get("state") == "BLOCKED"
    ]
    blocked_text = "، ".join(blocked) if blocked else "لا يوجد خيوط محجوبة حالياً"

    return (
        f"\n\n**حالة المحاكاة الآن:** الوضع `{mode}` | المخزن `{len(buf)}/{cap}` | "
        f"`empty={empty_c}`، `full={full_c}`، `mutex={mutex_owner}` | الخيوط المحجوبة: {blocked_text}."
    )


def answer_concept(
    query: str,
    state: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    q = query.lower().strip()
    live = _summarize_live_state(state)

    if any(k in q for k in ("حالة المحاكاة", "ماذا يحدث الان", "ماذا يحدث الآن", "الوضع الحالي", "status", "current state", "why blocked", "لماذا محجوب")):
        if live:
            return (
                "إليك قراءة مباشرة لما يحدث داخل المحاكاة الآن:"
                f"{live}\n\nيمكنك أن تطلب مني: «أبطئ المنتجين»، «سرّع المستهلكين»، أو «تقدم خطوة» لترى التغير مباشرة."
            )

    if any(k in q for k in ("critical", "قسم حرج", "منطقة حرجة")):
        item = CONCEPT_DETAILS["critical_section"]
        return f"**{item['title']}**\n{item['body']}\n\n*مثال:* {item['example']}{live}"

    if any(k in q for k in ("semaphore", "mutex", "empty", "full", "سيمافور", "قفل")):
        item = CONCEPT_DETAILS["semaphore"]
        return f"**{item['title']}**\n{item['body']}\n\n*مثال:* {item['example']}{live}"

    if any(k in q for k in ("race", "سباق", "تضارب")):
        item = CONCEPT_DETAILS["race_condition"]
        return f"**{item['title']}**\n{item['body']}\n\n*مثال:* {item['example']}{live}"

    if any(k in q for k in ("overflow", "underflow", "فيض", "نقص", "امتلاء", "فارغ")):
        item = CONCEPT_DETAILS["overflow_underflow"]
        return f"**{item['title']}**\n{item['body']}\n\n*مثال:* {item['example']}{live}"

    if any(k in q for k in ("running", "blocked", "حالة", "حالات", "محجوب", "يعمل")):
        item = CONCEPT_DETAILS["states"]
        return f"**{item['title']}**\n{item['body']}\n\n*مثال:* {item['example']}{live}"

    if any(k in q for k in ("ترتيب", "deadlock", "استعصاء", "order", "لماذا")):
        item = CONCEPT_DETAILS["deadlock_order"]
        return f"**{item['title']}**\n{item['body']}\n\n*مثال:* {item['example']}{live}"

    if any(g in q for g in ("مرحبا", "اهلا", "أهلا", "السلام", "hi", "hello", "كيف حالك")):
        return (
            "أهلاً بك! أنا مساعدك التفاعلي لمحاكاة **Producer–Consumer** وأنظمة التشغيل.\n"
            "يمكننا أن نناقش مفاهيم التزامن (`Critical Section`، `Semaphores`، `Mutex`، `Race Condition`، `Overflow/Underflow`)، "
            "أو يمكنك أن تعطيني أمراً مباشراً مثل: **«أبطئ المنتجين»**، **«سرّع المستهلكين»**، **«شغّل المحاكاة»**، أو **«تقدم خطوة»**."
            f"{live}"
        )

    last_user_note = ""
    if history and len(history) >= 2:
        prev_topics = [m.get("content", "") for m in history[-4:-1] if m.get("role") == "user"]
        if prev_topics:
            last_user_note = f"\n\nبناءً على سياق حديثنا السابق، "

    return (
        f"{last_user_note}سؤالك يرتبط بمزامنة العمليات/الخيوط في المخزن المحدود. "
        "وضّح أكثر إن كنت تقصد: **القسم الحرج (`Critical Section`)**، **السيمافور و`mutex`**، "
        "**حالة السباق (`Race Condition`)**، **الفيض/النقص (`Overflow/Underflow`)**، أو **حالات `RUNNING` و`BLOCKED`**، "
        "أو اكتب أمراً لتعديل سرعة أو تشغيل المحاكاة."
        f"{live}"
    )
