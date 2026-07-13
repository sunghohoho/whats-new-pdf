// ── 상태 (단일 소스) ─────────────────────────────────────────
let state = {
  meta: { eyebrow: "Infrastructure Notice", title: "AWS 서비스 변경사항 안내",
          subtitle: "", author: "MSP", written: "", intro: "" },
  eol_eos: [],
  whats_new: [],
};

const $ = (s, r = document) => r.querySelector(s);
const el = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };

// ── 미리보기 (debounced) ─────────────────────────────────────
let pvTimer = null;
function schedulePreview() {
  $("#pvStatus").textContent = "갱신 중…";
  clearTimeout(pvTimer);
  pvTimer = setTimeout(refreshPreview, 350);
}
async function refreshPreview() {
  try {
    const res = await fetch("/api/preview", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state),
    });
    const html = await res.text();
    const iframe = $("#preview");
    iframe.srcdoc = html;
    iframe.onload = () => {
      try {
        const h = iframe.contentDocument.body.scrollHeight;
        iframe.style.height = Math.max(h, 1123) + "px";
      } catch (e) {}
    };
    $("#pvStatus").textContent = "최신";
  } catch (e) {
    $("#pvStatus").textContent = "미리보기 오류";
  }
}

function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2000);
}

// ── meta 바인딩 ──────────────────────────────────────────────
function bindMeta() {
  document.querySelectorAll("[data-meta]").forEach((inp) => {
    inp.value = state.meta[inp.dataset.meta] || "";
    inp.addEventListener("input", () => {
      state.meta[inp.dataset.meta] = inp.value;
      schedulePreview();
    });
  });
}

// ── EOL/EOS 렌더 ─────────────────────────────────────────────
const BADGES_EOL = [["sunset", "SUNSET (EOL)"], ["eos", "EOS (변경/종료)"]];
function renderEol() {
  const list = $("#eolList"); list.innerHTML = "";
  state.eol_eos.forEach((item, i) => {
    const row = el("div", "row");
    row.innerHTML = `
      <div class="row-head">
        <span class="row-idx">#${i + 1}</span>
        <button class="icon-btn" data-del="${i}">삭제</button>
      </div>
      <label class="field"><span>서비스</span><input data-k="service"></label>
      <div class="grid-2">
        <label class="field"><span>대상 버전 · 항목</span><input data-k="target"></label>
        <label class="field"><span>종료 · 변경일</span><input data-k="date"></label>
      </div>
      <label class="field"><span>전환 대상 · 조치</span><input data-k="action"></label>
      <label class="field"><span>구분</span>
        <select class="badge-select" data-k="badge">
          ${BADGES_EOL.map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}
        </select>
      </label>`;
    row.querySelectorAll("[data-k]").forEach((inp) => {
      inp.value = item[inp.dataset.k] || "";
      inp.addEventListener("input", () => { item[inp.dataset.k] = inp.value; schedulePreview(); });
    });
    row.querySelector("[data-del]").addEventListener("click", () => {
      state.eol_eos.splice(i, 1); renderEol(); schedulePreview();
    });
    list.appendChild(row);
  });
}

// ── NEW 렌더 ─────────────────────────────────────────────────
const BADGES_NEW = [["", "없음"], ["GA", "GA"], ["PREVIEW", "PREVIEW"]];
function badgeSelect(k, val) {
  return `<select data-k="${k}">${BADGES_NEW.map(([v, t]) =>
    `<option value="${v}" ${v === (val||"") ? "selected" : ""}>${t}</option>`).join("")}</select>`;
}
function renderNew() {
  const list = $("#newList"); list.innerHTML = "";
  state.whats_new.forEach((item, i) => {
    item.subitems = item.subitems || [];
    const row = el("div", "row");
    row.innerHTML = `
      <div class="row-head">
        <span class="row-idx">#${i + 1}</span>
        <button class="icon-btn" data-del="${i}">삭제</button>
      </div>
      <label class="field"><span>제목</span><input data-k="title"></label>
      <div class="grid-2">
        <label class="field"><span>배지</span>${badgeSelect("badge", item.badge)}</label>
        <label class="field"><span>날짜</span><input data-k="date"></label>
      </div>
      <label class="field"><span>본문 (설명)</span><textarea data-k="body"></textarea></label>
      <label class="field"><span>URL</span><input data-k="url"></label>
      <div class="subitems" data-sub></div>
      <button class="add-btn" data-addsub style="margin-top:4px;">＋ 하위 항목 추가</button>`;

    row.querySelectorAll(":scope > label [data-k], :scope > .grid-2 [data-k]").forEach((inp) => {
      inp.value = item[inp.dataset.k] || "";
      inp.addEventListener("input", () => { item[inp.dataset.k] = inp.value; schedulePreview(); });
    });
    // select(badge)는 change 이벤트로도 반영
    row.querySelectorAll(":scope select[data-k]").forEach((s) => {
      s.addEventListener("change", () => { item[s.dataset.k] = s.value; schedulePreview(); });
    });

    // subitems
    const subWrap = row.querySelector("[data-sub]");
    function renderSubs() {
      subWrap.innerHTML = "";
      item.subitems.forEach((sub, j) => {
        const sr = el("div", "row");
        sr.style.background = "#fff";
        sr.innerHTML = `
          <div class="row-head"><span class="row-idx">하위 #${j + 1}</span>
            <button class="icon-btn" data-delsub="${j}">삭제</button></div>
          <label class="field"><span>소제목</span><input data-sk="subtitle"></label>
          <div class="grid-2">
            <label class="field"><span>배지</span>${badgeSelect("subbadge", sub.badge)}</label>
            <label class="field"><span>날짜</span><input data-sk="date"></label>
          </div>
          <label class="field"><span>본문</span><textarea data-sk="body"></textarea></label>
          <label class="field"><span>URL</span><input data-sk="url"></label>`;
        sr.querySelectorAll("[data-sk]").forEach((inp) => {
          inp.value = sub[inp.dataset.sk] || "";
          inp.addEventListener("input", () => { sub[inp.dataset.sk] = inp.value; schedulePreview(); });
        });
        sr.querySelector("select[data-k='subbadge']").addEventListener("change", (e) => {
          sub.badge = e.target.value; schedulePreview();
        });
        sr.querySelector("[data-delsub]").addEventListener("click", () => {
          item.subitems.splice(j, 1); renderSubs(); schedulePreview();
        });
        subWrap.appendChild(sr);
      });
    }
    renderSubs();
    row.querySelector("[data-addsub]").addEventListener("click", () => {
      item.subitems.push({ subtitle: "", badge: "", date: "", body: "", url: "" });
      renderSubs(); schedulePreview();
    });

    row.querySelector("[data-del]").addEventListener("click", () => {
      state.whats_new.splice(i, 1); renderNew(); schedulePreview();
    });
    list.appendChild(row);
  });
}

function renderAll() { bindMeta(); renderEol(); renderNew(); schedulePreview(); }

// ── 버튼 동작 ────────────────────────────────────────────────
$("#btnAddEol").addEventListener("click", () => {
  state.eol_eos.push({ service: "", target: "", date: "", action: "", badge: "sunset" });
  renderEol(); schedulePreview();
});
$("#btnAddNew").addEventListener("click", () => {
  state.whats_new.push({ title: "", badge: "", date: "", note: "", body: "", url: "", subitems: [] });
  renderNew(); schedulePreview();
});

$("#btnParse").addEventListener("click", async () => {
  const text = $("#scriptInput").value.trim();
  if (!text) { toast("스크립트를 먼저 붙여넣어 주세요"); return; }

  const btn = $("#btnParse");
  btn.disabled = true;
  const oldLabel = btn.textContent;
  btn.textContent = "파싱 중…";
  progressStart();

  try {
    const res = await fetch("/api/parse", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error("서버 오류 " + res.status);
    const data = await res.json();

    state.meta = { ...state.meta, ...data.meta };
    state.eol_eos = data.eol_eos || [];
    state.whats_new = (data.whats_new || []).map((x) => ({ subitems: [], ...x }));
    renderAll();

    const usedLlm = data._method === "llm";
    const tag = usedLlm ? "AI 파싱" : (CONFIG.llm_available ? "기본 파싱(폴백)" : "기본 파싱");
    const summary = `${tag} 완료 · 종료 ${state.eol_eos.length}건, 신규 ${state.whats_new.length}건`;
    progressFinish(true, summary);
    toast(summary);
    showUsage(data._usage, usedLlm);
    if (data._llm_error) {
      console.warn("LLM 파싱 실패 → 기본 파서로 폴백:", data._llm_error);
      toast("LLM 호출 실패 → 기본 파서로 처리했어요");
    }
  } catch (e) {
    progressFinish(false, "파싱 실패: " + e.message);
    toast("파싱 중 오류가 발생했습니다");
  } finally {
    btn.disabled = false;
    btn.textContent = oldLabel;
  }
});

$("#btnClear").addEventListener("click", () => {
  if (!confirm("모든 항목을 비울까요?")) return;
  state.eol_eos = []; state.whats_new = [];
  renderAll();
});

$("#btnPdf").addEventListener("click", async () => {
  const btn = $("#btnPdf");
  btn.disabled = true;
  const old = btn.innerHTML;

  try {
    // 1단계: URL 유효성 검사
    btn.innerHTML = '<span class="spinner"></span>링크 확인 중…';
    const chkRes = await fetch("/api/check-urls", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state),
    });
    const chkData = await chkRes.json();

    if (chkData.dead && chkData.dead.length > 0) {
      const deadList = chkData.dead.map(d => `• ${d.title || d.url} (${d.code || "unreachable"})`).join("\n");
      const proceed = confirm(
        `⚠️ 접근 불가 링크 ${chkData.dead.length}개가 발견됐어요:\n\n${deadList}\n\n계속 PDF를 생성할까요? (죽은 링크는 취소선으로 표시됩니다)`
      );
      if (!proceed) { btn.disabled = false; btn.innerHTML = old; return; }
    }

    // 2단계: PDF 생성 (서버에서 url_status 포함해 렌더링)
    btn.innerHTML = '<span class="spinner"></span>PDF 생성 중…';
    // check-urls 결과(url_status 포함된 data)를 그대로 PDF 요청에 활용
    const pdfState = chkData.data || state;
    const res = await fetch("/api/pdf", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pdfState),
    });
    if (!res.ok) throw new Error("생성 실패");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (state.meta.title || "aws-report").replace(/\s+/g, "_") + ".pdf";
    a.click();
    URL.revokeObjectURL(url);
    toast("PDF 다운로드 완료");
  } catch (e) {
    toast("PDF 생성 중 오류가 발생했습니다");
  } finally {
    btn.disabled = false; btn.innerHTML = old;
  }
});

$("#btnSample").addEventListener("click", () => loadSample());

// ── 샘플 ─────────────────────────────────────────────────────
async function loadSample() {
  const res = await fetch("/static/sample.json");
  state = await res.json();
  renderAll();
  toast("샘플을 불러왔습니다");
}

// ── LLM 사용 가능 여부 표시 ──────────────────────────────────
let CONFIG = { llm_available: false, llm_provider: "", llm_model_short: "" };
async function initConfig() {
  try {
    CONFIG = await (await fetch("/api/config")).json();
    const elp = $("#llmStatus");
    if (CONFIG.llm_available) {
      const m = CONFIG.llm_model_short ? ` · ${CONFIG.llm_model_short}` : "";
      elp.textContent = `AI 파싱 사용 (${CONFIG.llm_provider}${m})`;
      elp.className = "pill on";
    } else {
      elp.textContent = "기본 파싱 (규칙 기반)";
      elp.className = "pill off";
    }
  } catch (e) {}
}

// ── 진행 표시 헬퍼 ───────────────────────────────────────────
let progTimer = null;
function progressStart() {
  const box = $("#parseProgress");
  box.hidden = false;
  $("#progressSpin").style.display = "inline-block";
  const fill = $("#progressFill");
  fill.className = "progress-fill";
  fill.style.width = "6%";

  const t0 = Date.now();
  const llm = CONFIG.llm_available;
  const modelName = CONFIG.llm_model_short || CONFIG.llm_provider || "LLM";

  // 단계 메시지 (경과 시간 기반)
  const stages = llm
    ? [
        [0.0, "원본 텍스트 전송 중…"],
        [0.8, `Bedrock ${modelName} 호출 중…`],
        [6.0, `${modelName} 응답 분석 중…`],
        [12.0, "거의 다 됐어요…"],
      ]
    : [
        [0.0, "텍스트 파싱 중…"],
        [0.5, "항목 추출 중…"],
      ];

  clearInterval(progTimer);
  progTimer = setInterval(() => {
    const sec = (Date.now() - t0) / 1000;
    // 단계 메시지
    let msg = stages[0][1];
    for (const [th, m] of stages) if (sec >= th) msg = m;
    $("#progressMsg").textContent = msg;
    $("#progressTimer").textContent = sec.toFixed(1) + "s";
    // 진행 바: 90%까지 점근적으로 채움 (실제 완료 전까지)
    const target = llm ? 90 : 70;
    const pct = target * (1 - Math.exp(-sec / (llm ? 5 : 0.6)));
    $("#progressFill").style.width = Math.max(6, pct) + "%";
  }, 150);
}
function showUsage(usage, usedLlm) {
  const box = $("#lastUsage");
  if (!usedLlm || !usage || !usage.total) {
    box.hidden = true;
    return;
  }
  box.hidden = false;
  box.innerHTML =
    `<span>토큰 사용량</span>` +
    `<span class="chip">입력 <b>${usage.input.toLocaleString()}</b></span>` +
    `<span class="chip">출력 <b>${usage.output.toLocaleString()}</b></span>` +
    `<span class="chip">합계 <b>${usage.total.toLocaleString()}</b></span>`;
}

function progressFinish(ok, message) {
  clearInterval(progTimer);
  const fill = $("#progressFill");
  fill.className = "progress-fill " + (ok ? "done" : "error");
  fill.style.width = "100%";
  $("#progressSpin").style.display = "none";
  $("#progressMsg").textContent = message;
  setTimeout(() => { $("#parseProgress").hidden = true; }, 1600);
}

initConfig();
renderAll();
