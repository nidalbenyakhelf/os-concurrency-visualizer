const modePill = document.getElementById("mode-pill");
const tickPill = document.getElementById("tick-pill");
const bufferCounter = document.getElementById("buffer-counter");
const bufferSlots = document.getElementById("buffer-slots");
const producersMini = document.getElementById("producers-mini");
const consumersMini = document.getElementById("consumers-mini");
const workersDetailList = document.getElementById("workers-detail-list");
const eventLog = document.getElementById("event-log");
const chatStream = document.getElementById("chat-stream");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

const semEmptyVal = document.getElementById("sem-empty-val");
const semFullVal = document.getElementById("sem-full-val");
const semMutexVal = document.getElementById("sem-mutex-val");
const semMutexSub = document.getElementById("sem-mutex-sub");
const semEmptyCard = document.getElementById("sem-empty-card");
const semFullCard = document.getElementById("sem-full-card");
const semMutexCard = document.getElementById("sem-mutex-card");

const producerDelayInput = document.getElementById("producer-delay");
const consumerDelayInput = document.getElementById("consumer-delay");
const capacityInput = document.getElementById("capacity-input");

let lastTick = -1;
let prevEmpty = null;
let prevFull = null;
let topZ = 35;

function bumpSem(card) {
  card.classList.remove("bump");
  void card.offsetWidth;
  card.classList.add("bump");
}

function appendBubble(sender, text) {
  const el = document.createElement("div");
  el.className = `msg-bubble ${sender}`;
  el.textContent = text;
  chatStream.appendChild(el);
  chatStream.scrollTop = chatStream.scrollHeight;
}

function renderState(state) {
  if (!state || !state.workers) return;

  modePill.textContent = state.mode;
  tickPill.textContent = `TICK #${state.tick}`;

  const emptyCount = Number(state.empty_count ?? 0);
  const fullCount = Number(state.full_count ?? 0);
  semEmptyVal.textContent = String(emptyCount);
  semFullVal.textContent = String(fullCount);

  if (prevEmpty !== null && prevEmpty !== emptyCount) bumpSem(semEmptyCard);
  if (prevFull !== null && prevFull !== fullCount) bumpSem(semFullCard);
  prevEmpty = emptyCount;
  prevFull = fullCount;

  if (state.mutex_locked) {
    semMutexCard.classList.add("locked");
    semMutexVal.textContent = "LOCKED";
    semMutexSub.textContent = `داخل القسم الحرج: ${state.mutex_owner || "Thread"}`;
  } else {
    semMutexCard.classList.remove("locked");
    semMutexVal.textContent = "FREE";
    semMutexSub.textContent = "القسم الحرج متاح";
  }

  const items = state.buffer || [];
  const capacity = Number(state.capacity || 0);
  bufferCounter.textContent = `${items.length} / ${capacity}`;
  if (document.activeElement !== capacityInput && capacity > 0) {
    capacityInput.value = String(capacity);
  }

  bufferSlots.innerHTML = "";
  for (let i = 0; i < capacity; i += 1) {
    const cell = document.createElement("div");
    if (i < items.length) {
      cell.className = "buf-cell filled";
      cell.textContent = items[i];
    } else {
      cell.className = "buf-cell";
      cell.textContent = `Slot ${i + 1}\nفارغ`;
    }
    bufferSlots.appendChild(cell);
  }

  producersMini.innerHTML = "";
  consumersMini.innerHTML = "";
  workersDetailList.innerHTML = "";

  let syncedP = false;
  let syncedC = false;

  Object.values(state.workers).forEach((w) => {
    const mini = document.createElement("div");
    mini.className = `mini-worker ${w.state}`;
    mini.innerHTML = `<strong>${w.worker_id}</strong> · ${w.state}<br/><span>${w.last_action}</span>`;
    if (w.role === "PRODUCER") {
      producersMini.appendChild(mini);
      if (!syncedP && document.activeElement !== producerDelayInput) {
        producerDelayInput.value = Number(w.delay).toFixed(2);
        syncedP = true;
      }
    } else {
      consumersMini.appendChild(mini);
      if (!syncedC && document.activeElement !== consumerDelayInput) {
        consumerDelayInput.value = Number(w.delay).toFixed(2);
        syncedC = true;
      }
    }

    const detail = document.createElement("div");
    detail.className = `detail-card ${w.state}`;
    detail.innerHTML = `
      <div><strong>${w.worker_id}</strong> (${w.role}) — <strong>${w.state}</strong></div>
      <div>الخطوة: ${w.last_action} | التأخير: ${Number(w.delay).toFixed(2)}s</div>
      <div>السبب: ${w.reason}</div>
    `;
    workersDetailList.appendChild(detail);
  });

  if (state.tick !== lastTick) {
    eventLog.textContent = (state.logs || []).join("\n");
    eventLog.scrollTop = eventLog.scrollHeight;
    lastTick = state.tick;
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

async function sendPrompt(text) {
  const clean = text.trim();
  if (!clean) return;
  appendBubble("user", clean);

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: clean }),
  });
  if (res.ok) {
    const data = await res.json();
    appendBubble("bot", data.reply);
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
    // Server starting or stopping
  }
}

// Floating windows toggle and drag
document.querySelectorAll("[data-open-win]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const win = document.getElementById(btn.dataset.openWin);
    if (!win) return;
    win.classList.add("open");
    topZ += 1;
    win.style.zIndex = String(topZ);
  });
});

document.querySelectorAll("[data-close-win]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const win = document.getElementById(btn.dataset.closeWin);
    if (win) win.classList.remove("open");
  });
});

document.querySelectorAll(".floating-win").forEach((win) => {
  win.addEventListener("mousedown", () => {
    topZ += 1;
    win.style.zIndex = String(topZ);
  });

  const bar = win.querySelector(".draggable-bar");
  if (!bar) return;

  bar.addEventListener("mousedown", (e) => {
    if (e.target.closest("button")) return;
    const rect = win.getBoundingClientRect();
    const offsetX = e.clientX - rect.left;
    const offsetY = e.clientY - rect.top;

    function onMove(ev) {
      const winWidth = win.offsetWidth || rect.width;
      const winHeight = win.offsetHeight || rect.height;
      const nextLeft = Math.max(8, Math.min(window.innerWidth - winWidth - 8, ev.clientX - offsetX));
      const nextTop = Math.max(8, Math.min(window.innerHeight - winHeight - 8, ev.clientY - offsetY));
      win.style.left = `${nextLeft}px`;
      win.style.top = `${nextTop}px`;
    }

    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
});

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

document.getElementById("btn-apply-capacity").addEventListener("click", async () => {
  const cap = Math.max(2, Math.min(12, parseInt(capacityInput.value, 10) || 6));
  await sendControl({ action: "SET_CAPACITY", capacity: cap });
});

document.querySelectorAll(".pill-btn[data-prompt]").forEach((btn) => {
  btn.addEventListener("click", () => sendPrompt(btn.dataset.prompt || ""));
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const val = chatInput.value;
  chatInput.value = "";
  await sendPrompt(val);
});

appendBubble(
  "bot",
  "أهلاً بك! اسحب نوافذ الأدوات أو أغلقها، واسألني عن Semaphores و Critical Section أو أرسل أمراً للتحكم بالسرعة."
);
pollState();
setInterval(pollState, 350);
