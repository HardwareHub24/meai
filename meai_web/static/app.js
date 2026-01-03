/* meai_web/static/app.js */

const elChat = document.getElementById("chat");
const elInput = document.getElementById("userInput");
const elSend = document.getElementById("sendBtn");
const elSessionLabel = document.getElementById("sessionId");
const elBtnNotes = document.getElementById("downloadNotesBtn");
const elBtnClear = document.getElementById("clearChatBtn");

function uuidv4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

let sessionId = uuidv4();
let inflight = false;

function setSession(id) {
  sessionId = id;
  if (elSessionLabel) elSessionLabel.textContent = sessionId;
}
setSession(sessionId);

function scrollToBottom() {
  if (!elChat) return;
  elChat.scrollTop = elChat.scrollHeight;
}

function renderMarkdown(text) {
  const html = window.marked ? marked.parse(text || "") : (text || "");
  const div = document.createElement("div");
  div.className = "md";
  div.innerHTML = html;
  return div;
}

function addBubble(role, text, citations) {
  const row = document.createElement("div");
  row.className = `bubble-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.appendChild(renderMarkdown(text));

  // citations (optional)
  if (citations && citations.length) {
    const c = document.createElement("div");
    c.className = "citations";

    const title = document.createElement("div");
    title.className = "citTitle";
    title.textContent = "Citations";
    c.appendChild(title);

    const ul = document.createElement("ul");
    citations.forEach((x) => {
      const li = document.createElement("li");

      // Try to build something human readable even if the backend changes fields.
      const src = x.source_file || x.source || x.title || "source";
      const page =
        x.page !== undefined && x.page !== null ? ` p${x.page}` : "";
      const chunk =
        x.chunk_index !== undefined && x.chunk_index !== null
          ? ` chunk ${x.chunk_index}`
          : "";
      li.textContent = `${src}${page}${chunk}`;
      ul.appendChild(li);
    });

    c.appendChild(ul);
    bubble.appendChild(c);
  } else if (role === "assistant") {
    const c = document.createElement("div");
    c.className = "citations muted";
    c.textContent = "Citations: None";
    bubble.appendChild(c);
  }

  row.appendChild(bubble);
  elChat.appendChild(row);

  // math typesetting
  if (window.MathJax && window.MathJax.typesetPromise) {
    window.MathJax.typesetPromise([bubble]).catch(() => {});
  }

  scrollToBottom();
}

function addThinking() {
  removeThinking(); // prevent duplicates

  const row = document.createElement("div");
  row.className = "bubble-row assistant";
  row.id = "thinkingRow";

  const bubble = document.createElement("div");
  bubble.className = "bubble assistant pending";
  bubble.textContent = "Thinking…";

  row.appendChild(bubble);
  elChat.appendChild(row);
  scrollToBottom();
}

function removeThinking() {
  const row = document.getElementById("thinkingRow");
  if (row) row.remove();
}

// Robust error text extraction: prevents "Error: [object Object]"
async function parseResponse(res) {
  const raw = await res.text(); // always safe, even if server returns HTML
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = {};
  }
  return { raw, data };
}

async function sendMessage() {
  const msg = (elInput.value || "").trim();
  if (!msg || inflight) return;

  inflight = true;
  addBubble("user", msg);
  elInput.value = "";
  addThinking();

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "mode_1",            // <-- IMPORTANT: backend still requires this
        message: msg,
        session_id: sessionId
      }),
    });

    const raw = await res.text();
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; } catch {}

    removeThinking();

    if (!res.ok) {
      let detail = data.detail ?? raw ?? `HTTP ${res.status}`;
      if (typeof detail === "object") detail = JSON.stringify(detail, null, 2);
      addBubble("assistant", `Error: ${detail}`);
    } else {
      addBubble("assistant", data.answer || "", data.citations || []);
    }
  } catch (e) {
    removeThinking();
    const msg =
      (e && typeof e === "object" && e.message) ? e.message : JSON.stringify(e);
    addBubble("assistant", `Error: ${msg}`);
  } finally {
    inflight = false;
  }
}


if (elSend) elSend.addEventListener("click", sendMessage);

if (elInput) {
  elInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}

if (elBtnNotes) {
  elBtnNotes.addEventListener("click", () => {
    window.location.href = `/api/notes/download?session_id=${encodeURIComponent(
      sessionId
    )}`;
  });
}

if (elBtnClear) {
  elBtnClear.addEventListener("click", () => {
    elChat.innerHTML = "";
    setSession(uuidv4());
    elInput.focus();
  });
}
