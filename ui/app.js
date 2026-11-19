const modeBadge = document.getElementById("mode-badge");
const tickBadge = document.getElementById("tick-badge");
const bufferCount = document.getElementById("buffer-count");
const bufferSlots = document.getElementById("buffer-slots");
const workersList = document.getElementById("workers-list");
const eventLog = document.getElementById("event-log");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

const semEmptyVal = document.getElementById("sem-empty-val");
const semFullVal = document.getElementById("sem-full-val");
const semMutexVal = document.getElementById("sem-mutex-val");
const semMutexOwner = document.getElementById("sem-mutex-owner");
const semEmptyBox = document.getElementById("sem-empty-box");
const semFullBox = document.getElementById("sem-full-box");
const semMutexBox = document.getElementById("sem-mutex-box");

const producerDelayInput = document.getElementById("producer-delay");
const consumerDelayInput = document.getElementById("consumer-delay");

let lastTickSeen = -1;
let prevEmpty = null;
let prevFull = null;

function pulseBox(el) {
  el.classList.remove("pulse");
  void el.offsetWidth;
  el.classList.add("pulse");
}

function appendMessage(sender, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${sender}`;
  bubble.textContent = text;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderState(state) {
  if (!state || !state.workers) return;

  modeBadge.textContent = state.mode;
  modeBadge.className = `pill mode-${String(state.mode || "").toLowerCase()}`;
  tickBadge.textContent = `TICK #${state.tick}`;

  const emptyCount = Number(state.empty_count ?? 0);
  const fullCount = Number(state.full_count ?? 0);
  semEmptyVal.textContent = String(emptyCount);
  semFullVal.textContent = String(fullCount);

  if (prevEmpty !== null && prevEmpty !== emptyCount) pulseBox(semEmptyBox);
  if (prevFull !== null && prevFull !== fullCount) pulseBox(semFullBox);
  prevEmpty = emptyCount;
  prevFull = fullCount;

  if (state.mutex_locked) {
    semMutexBox.classList.add("locked");
    semMutexVal.textContent = "LOCKED";
    semMutexOwner.textContent = `داخل القسم الحرج: ${state.mutex_owner || "Thread"}`;
  } else {
    semMutexBox.classList.remove("locked");
    semMutexVal.textContent = "FREE";
    semMutexOwner.textContent = "القسم الحرج متاح";
  }

  const items = state.buffer || [];
  const capacity = Number(state.capacity || 0);
  bufferCount.textContent = `${items.length} / ${capacity}`;

  bufferSlots.innerHTML = "";
  for (let i = 0; i < capacity; i += 1) {
    const slot = document.createElement("div");
    if (i < items.length) {
      slot.className = "slot occupied";
      slot.textContent = items[i];
    } else {
      slot.className = "slot";
      slot.textContent = `Slot ${i + 1}\nفارغ`;
    }
    bufferSlots.appendChild(slot);
  }

  workersList.innerHTML = "";
  let syncedProducer = false;
  let syncedConsumer = false;

  Object.values(state.workers).forEach((w) => {
    const isMutexOwner = state.mutex_owner === w.worker_id;
    const card = document.createElement("div");
    card.className = `worker-card ${w.state}${isMutexOwner ? " mutex-active" : ""}`;
    const roleLabel = w.role === "PRODUCER" ? "منتِج (Producer)" : "مستهلِك (Consumer)";
    card.innerHTML = `
      <div class="worker-top">
        <span>${w.worker_id} — ${roleLabel}</span>
        <span class="badge-${w.state}">${w.state}</span>
      </div>
      <div class="worker-sub">الخطوة: <strong>${w.last_action}</strong> | التأخير: ${Number(w.delay).toFixed(2)}s</div>
      <div class="worker-sub">التفصيل: ${w.reason}</div>
    `;
    workersList.appendChild(card);

    if (w.role === "PRODUCER" && !syncedProducer && document.activeElement !== producerDelayInput) {
      producerDelayInput.value = Number(w.delay).toFixed(2);
      syncedProducer = true;
    }
    if (w.role === "CONSUMER" && !syncedConsumer && document.activeElement !== consumerDelayInput) {
      consumerDelayInput.value = Number(w.delay).toFixed(2);
      syncedConsumer = true;
    }
  });

  if (state.tick !== lastTickSeen) {
    eventLog.textContent = (state.logs || []).join("\n");
    eventLog.scrollTop = eventLog.scrollHeight;
    lastTickSeen = state.tick;
  }
}

async function sendControl(payload) {
  const res = await fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    renderState(await res.json());
  }
}

async function submitChatText(message) {
  const trimmed = message.trim();
  if (!trimmed) return;
  appendMessage("user", trimmed);

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: trimmed }),
  });
  if (res.ok) {
    const data = await res.json();
    appendMessage("bot", data.reply);
    if (data.state) {
      renderState(data.state);
    }
  }
}

async function pollState() {
  try {
    const res = await fetch("/api/state");
    if (res.ok) {
      renderState(await res.json());
    }
  } catch (_) {
    // Server starting or stopped
  }
}

document.getElementById("btn-play").addEventListener("click", () => sendControl({ action: "PLAY" }));
document.getElementById("btn-pause").addEventListener("click", () => sendControl({ action: "PAUSE" }));
document.getElementById("btn-step").addEventListener("click", () => sendControl({ action: "STEP", steps: 1 }));

document.getElementById("btn-apply-speed").addEventListener("click", async () => {
  await sendControl({
    action: "SET_SPEED",
    role: "PRODUCER",
    delay: parseFloat(producerDelayInput.value) || 1.0,
  });
  await sendControl({
    action: "SET_SPEED",
    role: "CONSUMER",
    delay: parseFloat(consumerDelayInput.value) || 1.2,
  });
});

document.querySelectorAll(".chip[data-prompt]").forEach((chip) => {
  chip.addEventListener("click", () => submitChatText(chip.dataset.prompt || ""));
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = chatInput.value;
  chatInput.value = "";
  await submitChatText(text);
});

appendMessage(
  "bot",
  "أهلاً بك! اسألني عن Semaphores و Critical Section و Race Condition أو اطلب مني التحكم بالسرعات والتشغيل."
);
pollState();
setInterval(pollState, 350);
