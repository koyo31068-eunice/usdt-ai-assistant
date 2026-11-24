/* =========================================================
   USDT AI 비서 - 프론트엔드 (바닐라 JavaScript)
   기능: 서버 깨우기 / 데이터 요약 / AI 채팅 / 대화 기록 / 데이터 관리(CRUD)
   ========================================================= */

// ---------------- 설정 ----------------
const API_BASE_URL = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000")
  .replace(/\/+$/, "");

const state = {
  convId: null,          // 지금 보고 있는 대화 id (null = 새 대화)
  messages: [],          // 지금 화면의 메시지
  rows: [],              // 데이터 전체 (날짜 오름차순)
  shown: 50,             // 데이터 목록에 보여 줄 개수
  editingId: null,       // 수정 중인 데이터 id
  sending: false,
};

const $ = (id) => document.getElementById(id);

// ---------------- 공통: API 호출 ----------------
async function api(path, { method = "GET", body, timeout = 20000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(API_BASE_URL + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(errorText(data, res.status));
    return data;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("서버 응답이 너무 늦습니다. 잠시 후 다시 시도하세요.");
    if (e instanceof TypeError) throw new Error("서버에 연결할 수 없습니다. 서버 주소와 실행 상태를 확인하세요.");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// FastAPI 오류 응답을 읽기 쉬운 문장으로 변환
function errorText(data, status) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => `${(d.loc || []).slice(-1)[0] || "입력"}: ${d.msg}`).join(" / ");
  }
  return `요청 실패 (HTTP ${status})`;
}

// ---------------- 공통: 화면 도우미 ----------------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// AI 답변의 **굵게** 와 줄바꿈만 표시 (HTML은 먼저 이스케이프해서 안전하게)
function renderText(s) {
  return escapeHtml(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
}

const won = (v) => (typeof v === "number" ? v.toLocaleString("ko-KR") : "-");

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

let toastTimer;
function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast" + (isError ? " error" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 3000);
}

function setStatus(text, kind) {
  const s = $("server-status");
  s.textContent = text;
  s.className = `status status-${kind}`;
}

// ---------------- 1) 서버 깨우기 (Render 콜드스타트 대응) ----------------
async function wakeServer() {
  setStatus("서버 확인 중", "wait");
  for (let i = 1; i <= 24; i++) {                       // 최대 약 2분
    try {
      await api("/health", { timeout: 8000 });
      $("wake-banner").hidden = true;
      setStatus("서버 연결됨", "ok");
      return true;
    } catch {
      $("wake-banner").hidden = false;
      $("wake-count").textContent = `(${i * 5}초 경과)`;
      setStatus("서버 깨우는 중", "wait");
      await new Promise((r) => setTimeout(r, 5000));
    }
  }
  setStatus("서버 연결 실패", "error");
  $("wake-banner").textContent = "서버에 연결하지 못했습니다. 페이지를 새로고침하거나 서버 상태를 확인하세요.";
  return false;
}

// ---------------- 2) 데이터 요약 ----------------
async function loadSummary() {
  try {
    const s = await api("/api/data/summary");
    renderSummary(s);
  } catch (e) {
    $("sum-trend").textContent = "요약을 불러오지 못했습니다: " + e.message;
  }
}

function renderSummary(s) {
  if (!s.count) {
    $("sum-trend").textContent = "저장된 데이터가 없습니다. 오른쪽에서 데이터를 추가하세요.";
    return;
  }
  const m = s.metrics;
  $("sum-latest").textContent = won(m.latest);
  $("sum-latest-at").textContent = `(${m.latest_at})`;
  const ch = $("sum-change");
  ch.textContent = `기간 시작(${won(m.first)}원) 대비 ${m.change_pct > 0 ? "+" : ""}${m.change_pct}%`;
  ch.className = "board-change " + (m.change_pct > 0 ? "up" : m.change_pct < 0 ? "down" : "");
  $("sum-trend").textContent = `추세: ${s.trend}`;
  $("sum-period").textContent = s.period;
  $("sum-count").textContent = `${s.count.toLocaleString()}개`;
  $("sum-avg").textContent = `${won(m.average)}원`;
  $("sum-max").textContent = `${won(m.max)}원 (${m.max_at.slice(5)})`;
  $("sum-min").textContent = `${won(m.min)}원 (${m.min_at.slice(5)})`;
  $("sum-premium").textContent = s.premium ? `${s.premium.average_pct > 0 ? "+" : ""}${s.premium.average_pct}%` : "-";
}

// 전체 가격 흐름 미니 차트 (SVG)
function drawSparkline() {
  const svg = $("sparkline");
  const vals = state.rows.map((r) => r.value);
  if (vals.length < 2) { svg.innerHTML = ""; return; }
  const W = 600, H = 120, pad = 8;
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const x = (i) => (i / (vals.length - 1)) * W;
  const y = (v) => H - pad - ((v - min) / span) * (H - pad * 2);
  const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const color = vals[vals.length - 1] >= vals[0] ? "var(--up)" : "var(--down)";
  const iMax = vals.indexOf(max), iMin = vals.indexOf(min);
  svg.innerHTML = `
    <line x1="0" x2="${W}" y1="${y(vals[0])}" y2="${y(vals[0])}" stroke="#cfd9d6" stroke-dasharray="4 4" />
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" />
    <circle cx="${x(iMax)}" cy="${y(max)}" r="4" fill="var(--up)" />
    <circle cx="${x(iMin)}" cy="${y(min)}" r="4" fill="var(--down)" />
    <circle cx="${x(vals.length - 1)}" cy="${y(vals[vals.length - 1])}" r="5" fill="var(--ink)" />`;
}

// ---------------- 3) AI 채팅 ----------------
function renderMessages() {
  const box = $("messages");
  box.innerHTML = "";
  if (!state.messages.length) {
    box.appendChild(emptyChat());
    return;
  }
  state.messages.forEach((m) => box.appendChild(messageEl(m)));
  box.scrollTop = box.scrollHeight;
}

function emptyChat() {
  const tpl = document.createElement("div");
  tpl.className = "chat-empty";
  tpl.innerHTML = `<p>저장된 USDT 데이터를 바탕으로 무엇이든 물어보세요.</p>
    <div class="chips">
      ${["최근 USDT 흐름 어때?", "가장 비쌌던 때는 언제야?", "11월 6일에는 무슨 일이 있었어?", "지금 신호는 Long이야 Short이야?"]
        .map((q) => `<button type="button" class="chip">${q}</button>`).join("")}
    </div>`;
  return tpl;
}

function messageEl(m) {
  const div = document.createElement("div");
  div.className = `msg msg-${m.role}`;
  div.innerHTML = renderText(m.content) + (m.created_at ? `<span class="msg-time">${fmtTime(m.created_at)}</span>` : "");
  return div;
}

async function sendMessage(text) {
  text = text.trim();
  if (!text || state.sending) return;
  state.sending = true;
  $("btn-send").disabled = true;
  $("chat-input").value = "";

  state.messages.push({ role: "user", content: text, created_at: new Date().toISOString() });
  renderMessages();

  // 로딩 표시
  const box = $("messages");
  const loading = document.createElement("div");
  loading.className = "msg msg-assistant msg-loading";
  loading.innerHTML = `데이터를 살펴보고 답변을 만드는 중<span class="dots"><span>.</span><span>.</span><span>.</span></span>`;
  box.appendChild(loading);
  box.scrollTop = box.scrollHeight;

  try {
    const res = await api("/api/chat", {
      method: "POST",
      body: state.convId ? { message: text, conversation_id: state.convId } : { message: text },
      timeout: 90000,
    });
    state.convId = res.conversation_id;
    state.messages.push({ role: "assistant", content: res.reply, created_at: new Date().toISOString() });
    renderMessages();
    loadConversations();                                  // 자동 저장된 대화를 목록에 반영
  } catch (e) {
    loading.remove();
    const err = document.createElement("div");
    err.className = "msg msg-error";
    err.textContent = "답변을 받지 못했습니다. " + e.message;
    box.appendChild(err);
    box.scrollTop = box.scrollHeight;
  } finally {
    state.sending = false;
    $("btn-send").disabled = false;
    $("chat-input").focus();
  }
}

function newChat() {
  state.convId = null;
  state.messages = [];
  $("chat-title").textContent = "새 대화";
  renderMessages();
  highlightConv();
  $("chat-input").focus();
}

// ---------------- 4) 대화 기록 ----------------
async function loadConversations() {
  const list = $("conv-list");
  try {
    const convs = await api("/api/conversations?limit=50");
    list.innerHTML = convs.length ? "" : `<li class="empty-note">아직 저장된 대화가 없습니다. 첫 질문을 보내 보세요.</li>`;
    convs.forEach((c) => {
      const li = document.createElement("li");
      li.className = "conv-item";
      li.dataset.id = c.id;
      li.tabIndex = 0;
      li.innerHTML = `
        <span class="conv-title">${escapeHtml(c.title)}</span>
        <span class="conv-meta">${fmtTime(c.updated_at)} · 메시지 ${c.message_count}개</span>
        <button class="conv-del" type="button" aria-label="대화 삭제">삭제</button>`;
      li.addEventListener("click", (e) => {
        if (e.target.classList.contains("conv-del")) deleteConversation(c.id);
        else openConversation(c.id);
      });
      li.addEventListener("keydown", (e) => { if (e.key === "Enter") openConversation(c.id); });
      list.appendChild(li);
    });
    highlightConv();
  } catch (e) {
    list.innerHTML = `<li class="empty-note">대화 목록을 불러오지 못했습니다: ${escapeHtml(e.message)}</li>`;
  }
}

function highlightConv() {
  document.querySelectorAll(".conv-item").forEach((li) => li.classList.toggle("active", li.dataset.id === state.convId));
}

async function openConversation(id) {
  try {
    const c = await api(`/api/conversations/${id}`);
    state.convId = c.id;
    state.messages = c.messages;
    $("chat-title").textContent = c.title;
    renderMessages();
    highlightConv();
    toast("대화를 불러왔습니다.");
  } catch (e) {
    toast(e.message, true);
  }
}

async function deleteConversation(id) {
  if (!confirm("이 대화를 삭제할까요? 삭제하면 되돌릴 수 없습니다.")) return;
  try {
    await api(`/api/conversations/${id}`, { method: "DELETE" });
    if (state.convId === id) newChat();
    toast("대화를 삭제했습니다.");
    loadConversations();
  } catch (e) {
    toast(e.message, true);
  }
}

// ---------------- 5) 데이터 관리 (CRUD) ----------------
async function loadData(flashId) {
  try {
    state.rows = await api("/api/data?limit=1000&order=asc");
    $("data-count").textContent = `총 ${state.rows.length}개`;
    renderDataList(flashId);
    drawSparkline();
  } catch (e) {
    $("data-list").innerHTML = `<li class="empty-note">데이터를 불러오지 못했습니다: ${escapeHtml(e.message)}</li>`;
  }
}

function renderDataList(flashId) {
  const list = $("data-list");
  const latestFirst = [...state.rows].reverse().slice(0, state.shown);
  list.innerHTML = latestFirst.length ? "" : `<li class="empty-note">데이터가 없습니다. 위 입력란에서 추가하세요.</li>`;
  latestFirst.forEach((r) => {
    const li = document.createElement("li");
    li.className = "data-row" + (r.id === flashId ? " flash" : "");
    li.innerHTML = `
      <div class="data-main">
        <span class="data-date">${r.date.replace("T", " ")}</span>
        <span class="data-value">${won(r.value)}원</span>
      </div>
      <span class="data-memo">${escapeHtml(r.memo || "")}</span>
      <div class="data-actions">
        <button type="button" class="edit">수정</button>
        <button type="button" class="del">삭제</button>
      </div>`;
    li.querySelector(".edit").addEventListener("click", () => startEdit(r));
    li.querySelector(".del").addEventListener("click", () => deleteData(r));
    list.appendChild(li);
  });
  $("btn-more").hidden = state.rows.length <= state.shown;
}

function startEdit(r) {
  state.editingId = r.id;
  $("f-date").value = r.date;
  $("f-value").value = r.value;
  $("f-memo").value = r.memo || "";
  $("data-form").classList.add("editing");
  $("btn-save").textContent = "수정 저장";
  $("btn-cancel").hidden = false;
  $("f-value").focus();
}

function resetForm() {
  state.editingId = null;
  $("data-form").reset();
  $("data-form").classList.remove("editing");
  $("btn-save").textContent = "데이터 추가";
  $("btn-cancel").hidden = true;
}

async function saveData(e) {
  e.preventDefault();
  const body = {
    date: $("f-date").value,
    value: Number($("f-value").value),
    memo: $("f-memo").value.trim(),
  };
  if (!body.date || !(body.value > 0)) {
    toast("시각과 0보다 큰 가격을 입력하세요.", true);
    return;
  }
  $("btn-save").disabled = true;
  try {
    let saved;
    if (state.editingId) {
      saved = await api(`/api/data/${state.editingId}`, { method: "PUT", body });
      toast(`수정했습니다: ${saved.date.replace("T", " ")} ${won(saved.value)}원`);
    } else {
      saved = await api("/api/data", { method: "POST", body });
      toast(`추가했습니다: ${saved.date.replace("T", " ")} ${won(saved.value)}원`);
    }
    resetForm();
    await loadData(saved.id);
    loadSummary();                                        // 요약도 즉시 갱신
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("btn-save").disabled = false;
  }
}

async function deleteData(r) {
  if (!confirm(`${r.date.replace("T", " ")} ${won(r.value)}원 데이터를 삭제할까요?`)) return;
  try {
    await api(`/api/data/${r.id}`, { method: "DELETE" });
    toast("삭제했습니다.");
    if (state.editingId === r.id) resetForm();
    await loadData();
    loadSummary();
  } catch (e) {
    toast(e.message, true);
  }
}

// ---------------- 이벤트 연결 ----------------
$("chat-form").addEventListener("submit", (e) => { e.preventDefault(); sendMessage($("chat-input").value); });
$("chat-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {   // 한글 조합 중 Enter 는 무시
    e.preventDefault();
    sendMessage($("chat-input").value);
  }
});
$("messages").addEventListener("click", (e) => {
  if (e.target.classList.contains("chip")) sendMessage(e.target.textContent);
});
$("btn-new-chat").addEventListener("click", newChat);
$("data-form").addEventListener("submit", saveData);
$("btn-cancel").addEventListener("click", resetForm);
$("btn-more").addEventListener("click", () => { state.shown += 50; renderDataList(); });
$("btn-refresh-summary").addEventListener("click", async () => {
  try {
    renderSummary(await api("/api/data/summary?refresh=true"));
    toast("요약을 새로 계산했습니다.");
  } catch (e) { toast(e.message, true); }
});

// ---------------- 시작 ----------------
(async function init() {
  if (await wakeServer()) {
    loadSummary();
    loadConversations();
    loadData();
  }
})();
