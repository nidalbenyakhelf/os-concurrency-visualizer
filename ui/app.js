cat << 'EOF' > ui/app.js
const modeBadge = document.getElementById("mode-badge");
const tickBadge = document.getElementById("tick-badge");
const bufferCount = document.getElementById("buffer-count");
const bufferSlots = document.getElementById("buffer-slots");
const workersList = document.getElementById("workers-list");
const eventLog = document.getElementById("event-log");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

const producerDelayInput = document.getElementById("producer-delay");
const consumerDelayInput = document.getElementById("consumer-delay");

function appendChat(sender, text) {
  const div = document.createElement("div");
  div.className = `chat-msg ${sender}`;
  div.textContent = `${sender === "user" ? "You" : "Assistant"}: ${text}`;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderState(state) {
  if (!state || !state.workers) return;

  modeBadge.textContent = `MODE: ${state.mode}`;
  tickBadge.textContent = `TICK: ${state.tick}`;

  const items = state.buffer || [];
  const capacity = state.capacity || 0;
  bufferCount.textContent = `${items.length}/${capacity}`;

  bufferSlots.innerHTML = "";
  for (let i = 0; i < capacity; i += 1) {
    const slot = document.createElement("div");
    if (i < items.length) {
      slot.className = "slot occupied";
      slot.textContent = items[i];
    } else {
      slot.className = "slot";
      slot.textContent = `Slot ${i + 1}\n(Empty)`;
    }
    bufferSlots.appendChild(slot);
  }

  workersList.innerHTML = "";
  let updatedProducer = false;
  let updatedConsumer = false;

  Object.values(state.workers).forEach((w) => {
    const card = document.createElement("div");
    card.className = `worker-card ${w.state}`;
    card.innerHTML = `
      <div class="worker-header">
        <span>${w.worker_id} (${w.role})</span>
        <span class="state-${w.state}">${w.state}</span>
      </div>
      <div class="worker-meta">Action: ${w.last_action} | Delay: ${Number(w.delay).toFixed(2)}s</div>
      <div class="worker-meta">Reason: ${w.reason}</div>
    `;
    workersList.appendChild(card);

    if (w.role === "PRODUCER" && !updatedProducer && document.activeElement !== producerDelayInput) {
      producerDelayInput.value = Number(w.delay).toFixed(2);
      updatedProducer = true;
    }
    if (w.role === "CONSUMER" && !updatedConsumer && document.activeElement !== consumerDelayInput) {
      consumerDelayInput.value = Number(w.delay).toFixed(2);
      updatedConsumer = true;
    }
  });

  eventLog.textContent = (state.logs || []).join("\n");
  eventLog.scrollTop = eventLog.scrollHeight;
}

async function sendControl(payload) {
  const res = await fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    const data = await res.json();
    renderState(data);
  }
}

async function pollState() {
  try {
    const res = await fetch("/api/state");
    if (res.ok) {
      const data = await res.json();
      renderState(data);
    }
  } catch (_) {
    // Server may be starting or stopping
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

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  appendChat("user", message);
  chatInput.value = "";

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (res.ok) {
    const data = await res.json();
    appendChat("bot", data.reply);
    if (data.state) {
      renderState(data.state);
    }
  }
});

appendChat("bot", "Ready. Ask about semaphores, critical sections, or command me to adjust speeds.");
pollState();
setInterval(pollState, 400);
EOF
