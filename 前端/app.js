const state = {
  activeScreen: "home",
  mood: "开心",
  images: [],
  selectedElement: null,
  savedPages: JSON.parse(localStorage.getItem("onepage_pages") || "[]")
};

const screens = document.querySelectorAll(".screen");
const navItems = document.querySelectorAll(".nav-item");
const toast = document.getElementById("toast");
const journalText = document.getElementById("journalText");
const imagePreview = document.getElementById("imagePreview");
const mainPhoto = document.getElementById("mainPhoto");
const toolPanel = document.getElementById("toolPanel");
const defaultPhoto = "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 150">
    <defs>
      <linearGradient id="sea" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stop-color="#b9dced"/>
        <stop offset="0.46" stop-color="#cce7f2"/>
        <stop offset="0.47" stop-color="#f2d8af"/>
        <stop offset="0.62" stop-color="#f7e3c5"/>
        <stop offset="0.63" stop-color="#83afc8"/>
        <stop offset="1" stop-color="#6f9bb8"/>
      </linearGradient>
    </defs>
    <rect width="120" height="150" fill="url(#sea)"/>
    <circle cx="88" cy="28" r="10" fill="#fff7d4"/>
    <path d="M8 82 C24 76, 42 88, 58 80 S94 75, 114 84" fill="none" stroke="#ffffff" stroke-width="3" opacity=".8"/>
    <path d="M52 118 q16 -22 32 0" fill="none" stroke="#2d4f62" stroke-width="3" stroke-linecap="round"/>
    <circle cx="68" cy="93" r="9" fill="#2f2b28"/>
  </svg>
`);

function showScreen(id) {
  state.activeScreen = id;
  screens.forEach((screen) => screen.classList.toggle("active", screen.id === id));
  navItems.forEach((item) => item.classList.toggle("active", item.dataset.target === id));
  if (id === "library") renderLibrary();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 1800);
}

document.querySelectorAll("[data-target]").forEach((control) => {
  control.addEventListener("click", () => showScreen(control.dataset.target));
});

journalText.addEventListener("input", () => {
  document.getElementById("count").textContent = journalText.value.length;
});

document.querySelectorAll(".mood").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".mood").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.mood = button.dataset.mood;
  });
});

document.getElementById("photoInput").addEventListener("change", (event) => {
  const files = [...event.target.files].slice(0, 4);
  files.forEach((file) => {
    const reader = new FileReader();
    reader.onload = () => {
      state.images.push(reader.result);
      renderImagePreview();
    };
    reader.readAsDataURL(file);
  });
});

function renderImagePreview() {
  imagePreview.innerHTML = "";
  state.images.slice(0, 4).forEach((src) => {
    const image = document.createElement("img");
    image.src = src;
    image.alt = "上传预览";
    imagePreview.appendChild(image);
  });
  if (state.images[0]) mainPhoto.src = state.images[0];
  else mainPhoto.src = defaultPhoto;
}

document.getElementById("generateBtn").addEventListener("click", () => {
  if (!journalText.value.trim()) {
    showToast("先写一点今天的记录吧");
    return;
  }
  showScreen("loading");
  startMockGeneration();
});

function startMockGeneration() {
  const progressBar = document.getElementById("progressBar");
  const progressText = document.getElementById("progressText");
  const loadingStep = document.getElementById("loadingStep");
  const steps = ["识别内容与照片", "分析心情与天气", "匹配手账素材", "生成版式 JSON", "渲染可编辑页面"];
  let value = 0;
  const timer = window.setInterval(() => {
    value += 8 + Math.floor(Math.random() * 12);
    const capped = Math.min(value, 100);
    progressBar.style.width = `${capped}%`;
    progressText.textContent = `${capped}%`;
    loadingStep.textContent = steps[Math.min(steps.length - 1, Math.floor(capped / 24))];
    if (capped >= 100) {
      window.clearInterval(timer);
      window.setTimeout(() => {
        applyGeneratedContent();
        showScreen("editor");
      }, 360);
    }
  }, 220);
}

function applyGeneratedContent() {
  const note = document.querySelector(".journal-page .note");
  note.textContent = journalText.value.trim();
  mainPhoto.src = state.images[0] || defaultPhoto;
}

function makeDraggable(element) {
  let startX = 0;
  let startY = 0;
  let originX = 0;
  let originY = 0;

  element.addEventListener("pointerdown", (event) => {
    selectElement(element);
    startX = event.clientX;
    startY = event.clientY;
    originX = parseFloat(element.style.left || 0);
    originY = parseFloat(element.style.top || 0);
    element.setPointerCapture(event.pointerId);
  });

  element.addEventListener("pointermove", (event) => {
    if (!element.hasPointerCapture(event.pointerId)) return;
    const nextX = originX + event.clientX - startX;
    const nextY = originY + event.clientY - startY;
    element.style.left = `${Math.max(0, Math.min(288, nextX))}px`;
    element.style.top = `${Math.max(0, Math.min(440, nextY))}px`;
  });
}

function selectElement(element) {
  document.querySelectorAll(".selected").forEach((item) => item.classList.remove("selected"));
  element.classList.add("selected");
  state.selectedElement = element;
}

document.querySelectorAll(".draggable, .editable").forEach((element) => {
  makeDraggable(element);
  element.addEventListener("click", () => selectElement(element));
});

document.querySelectorAll(".editable").forEach((element) => {
  element.addEventListener("dblclick", () => openPanel("text"));
});

document.querySelectorAll("[data-panel]").forEach((button) => {
  button.addEventListener("click", () => openPanel(button.dataset.panel));
});

function openPanel(type) {
  const closeButton = '<button class="icon-button" id="closePanel" title="关闭">×</button>';
  const templates = {
    stickers: `
      <div class="panel-head"><span>贴纸替换</span>${closeButton}</div>
      <div class="panel-grid">
        ${["✿", "❀", "❁", "✦", "☕", "camera", "memo", "bear", "paper"].map((item) => `<button class="sticker-option" data-sticker="${item}">${item}</button>`).join("")}
      </div>
    `,
    text: `
      <div class="panel-head"><span>文字编辑</span>${closeButton}</div>
      <textarea id="panelText">${(state.selectedElement?.textContent || "").trim()}</textarea>
      <button class="primary-action wide" id="applyText">应用文字</button>
    `,
    font: `
      <div class="panel-head"><span>字体</span>${closeButton}</div>
      ${["日系手写体", "清和手写体", "宋体", "思源宋体", "LXGW WenKai"].map((item) => `<button class="font-option" data-font="${item}">${item}</button>`).join("")}
      <div class="range-line"><span>Aa</span><input id="fontSize" type="range" min="12" max="38" value="24" /><span>＋</span></div>
    `,
    export: `
      <div class="panel-head"><span>导出手账</span>${closeButton}</div>
      <button class="export-option" id="exportPng">PNG 图片</button>
      <button class="export-option" id="exportPdf">PDF 文档</button>
      <p class="panel-tip">MVP 当前导出为可预览 SVG 图片，后续接入 canvas/Konva 后可替换为 Stage.toDataURL。</p>
    `,
    layout: `
      <div class="panel-head"><span>模板</span>${closeButton}</div>
      <div class="panel-grid">
        <button class="sticker-option" data-layout="sea">海边</button>
        <button class="sticker-option" data-layout="coffee">周末</button>
        <button class="sticker-option" data-layout="daily">日常</button>
      </div>
    `
  };

  toolPanel.innerHTML = templates[type] || "";
  toolPanel.classList.add("open");
  bindPanelEvents();
}

function bindPanelEvents() {
  document.getElementById("closePanel")?.addEventListener("click", () => toolPanel.classList.remove("open"));
  document.querySelectorAll("[data-sticker]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = state.selectedElement?.dataset.type === "sticker" ? state.selectedElement : document.querySelector(".flower-sticker");
      target.textContent = button.dataset.sticker;
      selectElement(target);
    });
  });
  document.getElementById("applyText")?.addEventListener("click", () => {
    if (!state.selectedElement || state.selectedElement.dataset.type !== "text") return;
    state.selectedElement.textContent = document.getElementById("panelText").value;
    toolPanel.classList.remove("open");
  });
  document.querySelectorAll("[data-font]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = state.selectedElement?.dataset.type === "text" ? state.selectedElement : document.querySelector(".note");
      target.style.fontFamily = fontStack(button.dataset.font);
    });
  });
  document.getElementById("fontSize")?.addEventListener("input", (event) => {
    const target = state.selectedElement?.dataset.type === "text" ? state.selectedElement : document.querySelector(".note");
    target.style.fontSize = `${event.target.value}px`;
  });
  document.getElementById("exportPng")?.addEventListener("click", exportPage);
  document.getElementById("exportPdf")?.addEventListener("click", () => showToast("PDF 导出会在后端导出服务接入后启用"));
}

function fontStack(fontName) {
  const map = {
    "日系手写体": '"Kaiti SC", "STKaiti", serif',
    "清和手写体": '"Hiragino Mincho ProN", "Songti SC", serif',
    "宋体": '"Songti SC", "STSong", serif',
    "思源宋体": '"Noto Serif SC", "Songti SC", serif',
    "LXGW WenKai": '"LXGW WenKai", "Kaiti SC", serif'
  };
  return map[fontName] || map["宋体"];
}

document.getElementById("savePage").addEventListener("click", () => {
  const item = {
    id: Date.now(),
    title: "2024 手账本",
    text: journalText.value.trim(),
    mood: state.mood,
    createdAt: new Date().toLocaleDateString("zh-CN")
  };
  state.savedPages.unshift(item);
  localStorage.setItem("onepage_pages", JSON.stringify(state.savedPages.slice(0, 12)));
  showToast("已保存到手账本");
});

function exportPage() {
  const text = document.querySelector(".note").textContent.replace(/[<>&]/g, "");
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="684" height="1000" viewBox="0 0 342 500">
      <rect width="342" height="500" rx="8" fill="#fffaf4"/>
      <text x="171" y="62" text-anchor="middle" font-size="30" font-family="serif" fill="#332b22">海边的</text>
      <text x="171" y="98" text-anchor="middle" font-size="30" font-family="serif" fill="#332b22">治愈时光</text>
      <rect x="46" y="120" width="112" height="154" fill="#ffffff"/>
      <rect x="54" y="128" width="96" height="126" fill="#9cc8dd"/>
      <rect x="178" y="112" width="122" height="166" fill="#ffffff" transform="rotate(9 239 195)"/>
      <text x="50" y="360" font-size="15" font-family="serif" fill="#4b4035">${text.slice(0, 58)}</text>
      <text x="50" y="390" font-size="15" font-family="serif" fill="#4b4035">${text.slice(58, 112)}</text>
    </svg>`;
  const blob = new Blob([svg], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "onepage-journal.svg";
  link.click();
  URL.revokeObjectURL(url);
  showToast("已导出图片");
}

function renderLibrary() {
  const bookshelf = document.getElementById("bookshelf");
  const months = document.getElementById("monthGrid");
  const pages = state.savedPages;
  bookshelf.innerHTML = `
    <div class="book saved"><strong>2024</strong><span>${pages.length || 1} 页</span></div>
    <div class="book"><strong>2023</strong><span>月拾光</span></div>
    <div class="book"><strong>2022</strong><span>旧时光</span></div>
    <button class="book add" data-target="create">＋<br />新建手账本</button>
  `;
  bookshelf.querySelector("[data-target]")?.addEventListener("click", () => showScreen("create"));
  months.innerHTML = Array.from({ length: 12 }, (_, index) => {
    const pageCount = index === 5 ? Math.max(1, pages.length) : Math.max(0, Math.floor(Math.random() * 4));
    return `<div class="month-card"><strong>${index + 1} 月</strong><p>${pageCount} 天记录</p><span>✿</span></div>`;
  }).join("");
}

renderImagePreview();
renderLibrary();
