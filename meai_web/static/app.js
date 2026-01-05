/* meai_web/static/app.js */

const elChat = document.getElementById("chat");
const elInput = document.getElementById("userInput");
const elSend = document.getElementById("sendBtn");
const elSessionLabel = document.getElementById("sessionId");
const elBtnNotes = document.getElementById("downloadNotesBtn");
const elNewChat = document.getElementById("newChatBtn");
const elChatList = document.getElementById("chatList");

function uuidv4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

const USER_ID_KEY = "meai_user_id";

function getOrCreateUserId() {
  try {
    const existing = window.localStorage.getItem(USER_ID_KEY);
    if (existing) return existing;
    const id =
      window.crypto && window.crypto.randomUUID
        ? window.crypto.randomUUID()
        : uuidv4();
    window.localStorage.setItem(USER_ID_KEY, id);
    return id;
  } catch {
    return uuidv4();
  }
}

const userId = getOrCreateUserId();

let sessionId = uuidv4();
let inflight = false;
let currentChatId = null;
let chatList = [];

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
  const html = window.marked ? marked.parse(text || "") : text || "";
  const div = document.createElement("div");
  div.className = "md";
  div.innerHTML = html;
  div.querySelectorAll("a").forEach((a) => {
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
  });
  return div;
}

const LATEX_MARKERS =
  /\\frac|\\int|\\sum|\\cdot|\\Delta|\\left|\\right|_|\\^|\\text|\\sqrt/;
const MATH_PLACEHOLDERS = {
  "\\[": "__MJX_LB__",
  "\\]": "__MJX_RB__",
  "\\(": "__MJX_LP__",
  "\\)": "__MJX_RP__",
};

function convertBracketMath(text) {
  if (!text) return text;
  let out = text;

  Object.entries(MATH_PLACEHOLDERS).forEach(([key, token]) => {
    out = out.replaceAll(key, token);
  });

  out = out.replace(/\[([\s\S]*?)\]/g, (m, inner) => {
    return LATEX_MARKERS.test(inner) ? `\\[${inner}\\]` : m;
  });
  out = out.replace(/\(([\s\S]*?)\)/g, (m, inner) => {
    return LATEX_MARKERS.test(inner) ? `\\(${inner}\\)` : m;
  });

  Object.entries(MATH_PLACEHOLDERS).forEach(([key, token]) => {
    out = out.replaceAll(token, key);
  });

  out = out.replace(/\\([\[\]\(\)])/g, "\\\\$1");
  return out;
}

const typesetQueue = [];
let typesetTimer = null;

function flushTypesetQueue() {
  if (!typesetQueue.length) return;
  if (!window.MathJax || !window.MathJax.typesetPromise) return;
  const targets = typesetQueue.splice(0);
  window.MathJax.typesetPromise(targets).catch(() => {});
}

function scheduleTypesetFlush() {
  if (typesetTimer) return;
  typesetTimer = setTimeout(() => {
    typesetTimer = null;
    flushTypesetQueue();
  }, 60);
}

function queueTypeset(target) {
  if (!target) return;
  typesetQueue.push(target);

  if (window.MathJax && window.MathJax.typesetPromise) {
    scheduleTypesetFlush();
    return;
  }

  if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) {
    window.MathJax.startup.promise
      .then(() => scheduleTypesetFlush())
      .catch(() => {});
    return;
  }

  setTimeout(() => {
    if (window.MathJax && window.MathJax.typesetPromise) {
      scheduleTypesetFlush();
    }
  }, 120);
}

function addBubble(role, text, citations) {
  const row = document.createElement("div");
  row.className = `bubble-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;

  const safeText = role === "assistant" ? convertBracketMath(text) : text;
  bubble.appendChild(renderMarkdown(safeText));

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
      const src = x.source_file || x.source || x.title || "source";
      const page = x.page !== undefined && x.page !== null ? ` p${x.page}` : "";
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

  queueTypeset(bubble);
  scrollToBottom();
}

function addThinking() {
  removeThinking();
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

function setActiveChat(chatId) {
  currentChatId = chatId;
  if (chatId) setSession(chatId);
  if (!elChatList) return;
  elChatList.querySelectorAll("li").forEach((li) => {
    li.classList.toggle("active", li.dataset.chatId === chatId);
  });
}

function renderChatList(chats) {
  if (!elChatList) return;
  elChatList.innerHTML = "";

  chats.forEach((chat) => {
    const li = document.createElement("li");
    li.dataset.chatId = chat.id;

    const title = document.createElement("span");
    title.className = "chat-title";
    title.textContent = chat.title || "New chat";

    const del = document.createElement("button");
    del.className = "chat-del";
    del.type = "button";
    del.title = "Delete chat";
    del.textContent = "🗑";

    del.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm("Delete this chat permanently?")) return;

      const res = await fetch(
        `/api/chats/${encodeURIComponent(chat.id)}?user_id=${encodeURIComponent(userId)}`,
        { method: "DELETE" }
      );

      if (!res.ok) return;

      if (currentChatId === chat.id) {
        currentChatId = null;
        elChat.innerHTML = "";
        setSession(uuidv4());
      }

      await refreshChatList({ preserveSelection: false });
    });

    li.addEventListener("click", async () => {
      await loadChat(chat.id);
      setActiveChat(chat.id);
    });

    li.appendChild(title);
    li.appendChild(del);
    elChatList.appendChild(li);
  });
}

async function refreshChatList({ preserveSelection } = {}) {
  try {
    const res = await fetch(`/api/chats?user_id=${encodeURIComponent(userId)}`);
    if (!res.ok) return;
    const data = await res.json();
    chatList = data.chats || [];
    renderChatList(chatList);

    if (!preserveSelection && !currentChatId && chatList.length) {
      await loadChat(chatList[0].id);
    }
  } catch {
    // ignore
  }
}

async function loadChat(chatId) {
  try {
    const res = await fetch(
      `/api/chats/${encodeURIComponent(chatId)}/messages?user_id=${encodeURIComponent(userId)}`
    );
    if (!res.ok) return;
    const data = await res.json();
    const messages = data.messages || [];
    elChat.innerHTML = "";
    messages.forEach((msg) => {
      const role = msg.role === "user" ? "user" : "assistant";
      addBubble(role, msg.content || "", []);
    });
    setActiveChat(chatId);
  } catch {
    // ignore
  }
}

async function createChat(title) {
  try {
    const res = await fetch("/api/chats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, title }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.chat?.id || null;
  } catch {
    return null;
  }
}

async function appendMessage(chatId, role, content) {
  try {
    await fetch(`/api/chats/${encodeURIComponent(chatId)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, role, content }),
    });
  } catch {
    // ignore
  }
}

async function newChat() {
  const chatId = await createChat();
  if (!chatId) return false;
  setActiveChat(chatId);
  await loadChat(chatId);
  await refreshChatList({ preserveSelection: true });
  if (elInput) elInput.focus();
  return true;
}

async function sendMessage() {
  const msg = (elInput.value || "").trim();
  if (!msg || inflight) return;

  inflight = true;
  addBubble("user", msg);
  elInput.value = "";
  addThinking();

  try {
    let activeChatId = currentChatId;
    let historyOk = true;

    if (!activeChatId) {
      activeChatId = await createChat();
      if (activeChatId) {
        setActiveChat(activeChatId);
        await refreshChatList({ preserveSelection: true });
      } else {
        historyOk = false;
      }
    }

    if (historyOk && activeChatId) {
      await appendMessage(activeChatId, "user", msg);
    }

    const lower = msg.toLowerCase();
    if (lower.startsWith("solve:") || lower.startsWith("simplify:")) {
      const task = lower.startsWith("solve:") ? "solve" : "simplify";
      const expr = msg.slice(task.length + 1).trim();

      const res = await fetch("/api/math", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task, expr, var: "x" }),
      });

      const raw = await res.text();
      let data = {};
      try {
        data = raw ? JSON.parse(raw) : {};
      } catch {
        data = {};
      }

      removeThinking();
      const out = data.result ?? data.error ?? "";
      addBubble("assistant", out);

      if (historyOk && activeChatId) {
        await appendMessage(activeChatId, "assistant", out || "");
        await refreshChatList({ preserveSelection: true });
      }
      return;
    }

    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "mode_1",
        message: msg,
        session_id: sessionId,
      }),
    });

    const raw = await res.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = {};
    }

    removeThinking();

    if (!res.ok) {
      let detail = data.detail ?? raw ?? `HTTP ${res.status}`;
      if (typeof detail === "object") detail = JSON.stringify(detail, null, 2);
      addBubble("assistant", `Error: ${detail}`);
    } else {
      addBubble("assistant", data.answer || "", data.citations || []);
      if (historyOk && activeChatId) {
        await appendMessage(activeChatId, "assistant", data.answer || "");
        await refreshChatList({ preserveSelection: true });
      }
    }
  } catch (e) {
    removeThinking();
    const emsg =
      e && typeof e === "object" && e.message ? e.message : JSON.stringify(e);
    addBubble("assistant", `Error: ${emsg}`);
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

if (elNewChat) {
  elNewChat.addEventListener("click", () => {
    newChat();
  });
}

refreshChatList();
