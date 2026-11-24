// Gov Policy Copilot - minimal bilingual SPA (no build step).
const I18N = {
  en: {
    title: "Gov Policy Copilot",
    subtitle: "Grounded answers from public UAE policy documents",
    tabChat: "Ask", tabReviews: "Review queue", signIn: "Sign in", signOut: "Sign out",
    heroTitle: "Ask about UAE AI & data policy",
    heroText: "Answers come only from official public documents, every sentence is cited, and low-confidence answers go to a human reviewer.",
    placeholder: "Ask in English or Arabic…",
    disclaimer: "Reference implementation on public data. Not an official government service and not legal advice.",
    reviewsTitle: "Human review queue", refresh: "Refresh",
    steps: { planning: "Planning", retrieving: "Searching documents", answering: "Writing answer", verifying: "Checking sources" },
    outcome: { answered: "Verified", escalated: "Sent to human review", not_found: "Not in documents", out_of_scope: "Out of scope", blocked: "Blocked by safety filter" },
    grounded: "Groundedness", sources: "Sources", page: "page", open: "Open document",
    approve: "Approve", reject: "Reject", noReviews: "Nothing waiting for review.", draft: "Draft answer", reason: "Reason",
    error: "Something went wrong. Please try again.",
    suggestions: [
      ["AI Charter", "What does the UAE AI Charter say about human oversight?"],
      ["Transparency", "How should AI decisions be explained under UAE principles?"],
      ["بالعربية", "ما هي مبادئ ميثاق الإمارات لتطوير واستخدام الذكاء الاصطناعي؟"],
      ["International stance", "What is the UAE's international position on AI policy?"],
    ],
  },
  ar: {
    title: "مساعد السياسات الحكومية",
    subtitle: "إجابات موثّقة من وثائق السياسات الإماراتية العامة",
    tabChat: "اسأل", tabReviews: "قائمة المراجعة", signIn: "تسجيل الدخول", signOut: "تسجيل الخروج",
    heroTitle: "اسأل عن سياسات الذكاء الاصطناعي والبيانات في الإمارات",
    heroText: "الإجابات مستمدة فقط من الوثائق الرسمية العامة، وكل جملة موثّقة بمصدرها، والإجابات منخفضة الثقة تُحال إلى مراجع بشري.",
    placeholder: "اكتب سؤالك بالعربية أو الإنجليزية…",
    disclaimer: "تطبيق مرجعي على بيانات عامة. ليس خدمة حكومية رسمية ولا يُعدّ استشارة قانونية.",
    reviewsTitle: "قائمة المراجعة البشرية", refresh: "تحديث",
    steps: { planning: "التخطيط", retrieving: "البحث في الوثائق", answering: "صياغة الإجابة", verifying: "التحقق من المصادر" },
    outcome: { answered: "تم التحقق", escalated: "أُحيلت للمراجعة البشرية", not_found: "غير موجود في الوثائق", out_of_scope: "خارج النطاق", blocked: "حُظر بواسطة مرشح الأمان" },
    grounded: "الاستناد للمصادر", sources: "المصادر", page: "صفحة", open: "فتح الوثيقة",
    approve: "اعتماد", reject: "رفض", noReviews: "لا توجد عناصر بانتظار المراجعة.", draft: "مسودة الإجابة", reason: "السبب",
    error: "حدث خطأ. يرجى المحاولة مرة أخرى.",
    suggestions: [
      ["الميثاق", "ما هي مبادئ ميثاق الإمارات لتطوير واستخدام الذكاء الاصطناعي؟"],
      ["الشفافية", "ما موقف الإمارات من الشفافية في الذكاء الاصطناعي؟"],
      ["English", "What does the UAE AI Charter say about human oversight?"],
      ["الخصوصية", "كيف يحمي الميثاق خصوصية الأفراد؟"],
    ],
  },
};

const $ = (s) => document.querySelector(s);
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
};
const isArabic = (t) => (t.match(/[؀-ۿ]/g) || []).length > (t.match(/[A-Za-z]/g) || []).length;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let lang = store.get("lang") || "en";
let auth = { enabled: false, msal: null, account: null, scope: "" };
const t = () => I18N[lang];

// ---------- i18n / theme ----------
function applyLang() {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t()[el.dataset.i18n]; });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t()[el.dataset.i18nPh]; });
  $("#langToggle").textContent = lang === "ar" ? "EN" : "ع";
  document.title = lang === "ar" ? "مساعد السياسات الحكومية · الإمارات" : "Gov Policy Copilot · UAE Policy Assistant";
  renderSuggestions();
}
function renderSuggestions() {
  const box = $("#suggestions");
  if (!box) return;
  box.innerHTML = "";
  t().suggestions.forEach(([tag, q], i) => {
    const b = document.createElement("button");
    b.className = "suggestion";
    b.style.animationDelay = `${0.1 + i * 0.08}s`;
    b.innerHTML = `<small>${esc(tag)}</small>${esc(q)}`;
    b.dir = isArabic(q) ? "rtl" : "ltr";
    b.onclick = () => ask(q);
    box.appendChild(b);
  });
}
$("#langToggle").onclick = () => { lang = lang === "en" ? "ar" : "en"; store.set("lang", lang); applyLang(); };
const savedTheme = store.get("theme");
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
$("#themeToggle").onclick = () => {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  store.set("theme", next);
};

// ---------- tabs ----------
document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === tab));
    $("#chatView").hidden = tab.dataset.view !== "chat";
    $("#reviewsView").hidden = tab.dataset.view !== "reviews";
    $("#composer").hidden = tab.dataset.view !== "chat";
    if (tab.dataset.view === "reviews") loadReviews();
  };
});

// ---------- auth (MSAL, only when enabled server-side) ----------
async function initAuth() {
  const cfg = await fetch("/api/config").then((r) => r.json());
  auth.enabled = cfg.authEnabled;
  if (!auth.enabled) { await refreshRoles(); return; }
  const msal = await import("https://cdn.jsdelivr.net/npm/@azure/msal-browser@3.27.0/+esm");
  auth.scope = cfg.apiScope;
  auth.msal = new msal.PublicClientApplication({
    auth: { clientId: cfg.clientId, authority: `https://login.microsoftonline.com/${cfg.tenantId}`, redirectUri: location.origin },
    cache: { cacheLocation: "sessionStorage" },
  });
  await auth.msal.initialize();
  const res = await auth.msal.handleRedirectPromise();
  auth.account = res?.account || auth.msal.getAllAccounts()[0] || null;
  const btn = $("#loginBtn");
  btn.hidden = false;
  btn.textContent = auth.account ? t().signOut : t().signIn;
  btn.onclick = () => auth.account ? auth.msal.logoutRedirect() : auth.msal.loginRedirect({ scopes: [auth.scope] });
  if (auth.account) await refreshRoles();
}
async function token() {
  if (!auth.enabled || !auth.account) return null;
  const r = await auth.msal.acquireTokenSilent({ scopes: [auth.scope], account: auth.account });
  return r.accessToken;
}
async function api(path, opts = {}) {
  const tk = await token();
  const headers = { "Content-Type": "application/json", ...(tk ? { Authorization: `Bearer ${tk}` } : {}) };
  return fetch(path, { ...opts, headers });
}
async function refreshRoles() {
  const r = await api("/me");
  if (!r.ok) return;
  const me = await r.json();
  $("#reviewsTab").hidden = !me.roles.some((x) => x === "Copilot.Reviewer" || x === "Copilot.Admin");
}

// ---------- chat ----------
function addMessage(role, text = "") {
  $("#hero")?.remove();
  const node = $("#msgTpl").content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  const content = node.querySelector(".content");
  content.textContent = text;
  content.dir = isArabic(text) ? "rtl" : "ltr";
  $("#messages").appendChild(node);
  node.scrollIntoView({ behavior: "smooth", block: "end" });
  return node;
}

function renderAnswer(node, result) {
  const bubble = node.querySelector(".bubble");
  const content = node.querySelector(".content");
  content.classList.remove("typing");
  content.dir = result.language === "ar" ? "rtl" : "ltr";
  content.innerHTML = esc(result.answer).replace(/\[(\d+)\]/g, '<span class="cite-ref" data-n="$1">$1</span>');

  const meta = document.createElement("div");
  meta.className = "meta";
  const cls = { answered: "ok", escalated: "warn", not_found: "warn", out_of_scope: "warn", blocked: "bad" }[result.outcome];
  meta.innerHTML = `<span class="badge ${cls}">${esc(t().outcome[result.outcome] || result.outcome)}</span>`;
  if (result.verification) meta.innerHTML += `<span class="badge">${t().grounded}: ${Math.round(result.verification.groundedness * 100)}%</span>`;
  meta.innerHTML += `<span class="badge">${(result.latency_ms / 1000).toFixed(1)}s</span><span class="badge">${esc(result.model)} · prompt ${esc(result.prompt_version)}</span>`;
  bubble.appendChild(meta);

  if (result.citations?.length) {
    const list = document.createElement("div");
    list.className = "citations";
    result.citations.forEach((c) => {
      const d = document.createElement("details");
      d.className = "citation";
      d.id = `cite-${result.request_id}-${c.n}`;
      d.innerHTML = `<summary><span class="n">[${c.n}]</span><span>${esc(c.title)}</span><span class="where">· ${t().page} ${c.page}</span></summary>
        <p dir="${isArabic(c.snippet) ? "rtl" : "ltr"}">${esc(c.snippet)}…</p><a href="${esc(c.source_url)}" target="_blank" rel="noopener">${t().open} ↗</a>`;
      list.appendChild(d);
    });
    bubble.appendChild(list);
    content.querySelectorAll(".cite-ref").forEach((ref) => {
      ref.onclick = () => {
        const el = document.getElementById(`cite-${result.request_id}-${ref.dataset.n}`);
        if (!el) return;
        el.open = true;
        el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
        el.scrollIntoView({ behavior: "smooth", block: "nearest" });
      };
    });
  }
  node.scrollIntoView({ behavior: "smooth", block: "end" });
}

async function ask(question) {
  question = question.trim();
  if (!question) return;
  $("#question").value = "";
  $("#sendBtn").disabled = true;
  addMessage("user", question);
  const node = addMessage("bot", "");
  const bubble = node.querySelector(".bubble");
  const content = node.querySelector(".content");
  const steps = document.createElement("div");
  steps.className = "steps";
  bubble.prepend(steps);
  content.classList.add("typing");
  content.dir = isArabic(question) ? "rtl" : "ltr";

  const setStep = (name) => {
    steps.querySelectorAll(".step.active").forEach((s) => { s.classList.remove("active"); s.classList.add("done"); });
    const s = document.createElement("span");
    s.className = "step active";
    s.textContent = t().steps[name] || name;
    steps.appendChild(s);
  };

  try {
    const res = await api("/api/chat/stream", { method: "POST", body: JSON.stringify({ question }) });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    let streamed = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const frames = buf.split(/\r?\n\r?\n/);
      buf = frames.pop();
      for (const frame of frames) {
        const data = frame.split(/\r?\n/).filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trimStart()).join("\n");
        if (!data) continue;
        const ev = JSON.parse(data);
        if (ev.type === "status") setStep(ev.step);
        else if (ev.type === "token") { streamed += ev.text; content.textContent = streamed; }
        else if (ev.type === "final") {
          steps.querySelectorAll(".step.active").forEach((s) => { s.classList.remove("active"); s.classList.add("done"); });
          renderAnswer(node, ev.result);
        }
      }
    }
  } catch (err) {
    content.classList.remove("typing");
    content.textContent = t().error;
    console.error(err);
  } finally {
    $("#sendBtn").disabled = false;
    $("#question").focus();
  }
}

$("#composer").onsubmit = (e) => { e.preventDefault(); ask($("#question").value); };
$("#question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(e.target.value); }
});
$("#question").addEventListener("input", (e) => {
  e.target.style.height = "auto";
  e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  e.target.dir = isArabic(e.target.value) ? "rtl" : "auto";
});

// ---------- review queue ----------
async function loadReviews() {
  const list = $("#reviewList");
  const r = await api("/api/reviews?status=pending");
  const items = r.ok ? await r.json() : [];
  list.innerHTML = items.length ? "" : `<div class="empty">${t().noReviews}</div>`;
  items.forEach((it) => {
    const el = document.createElement("div");
    el.className = "review";
    el.innerHTML = `<h3 dir="${isArabic(it.question_masked) ? "rtl" : "ltr"}">${esc(it.question_masked)}</h3>
      <div class="reason">${t().reason}: ${esc(it.reason)}</div>
      <textarea dir="${isArabic(it.draft_answer) ? "rtl" : "ltr"}">${esc(it.draft_answer)}</textarea>
      <div class="row"><button class="pill btn-ok">${t().approve}</button><button class="pill btn-no">${t().reject}</button></div>`;
    const decide = async (approve) => {
      await api(`/api/reviews/${it.id}`, { method: "POST", body: JSON.stringify({ approve, final_answer: el.querySelector("textarea").value }) });
      el.style.opacity = "0"; setTimeout(loadReviews, 250);
    };
    el.querySelector(".btn-ok").onclick = () => decide(true);
    el.querySelector(".btn-no").onclick = () => decide(false);
    list.appendChild(el);
  });
}
$("#refreshReviews").onclick = loadReviews;

applyLang();
initAuth().catch(console.error);
