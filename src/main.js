import "./styles/base.css";
import "./styles/proto-a.css";
import "./styles/proto-b.css";
import "./styles/proto-c.css";

import dataset from "./data/episodes.json";
import { getAudioState, stopPreview, subscribeAudio, togglePreview } from "./audio.js";
import {
  renderAudioDock,
  renderPrototypeA,
  renderPrototypeB,
  renderPrototypeC,
  renderTopBar,
} from "./render.js";

function readInitialProto() {
  const params = new URLSearchParams(window.location.search);
  const qp = params.get("proto");
  if (qp === "a" || qp === "b" || qp === "c") return qp;
  const hash = window.location.hash.replace("#", "").toLowerCase();
  if (hash === "a" || hash === "b" || hash === "c") return hash;
  return "a";
}

const state = {
  proto: readInitialProto(),
  category: "全部",
  query: "",
  activeId: dataset.episodes[0]?.id ?? 1,
  audioState: getAudioState(),
};

const app = document.getElementById("app");
const showToolbar = dataset.episodes.length > 5;

function filterEpisodes() {
  const q = state.query.trim().toLowerCase();
  return dataset.episodes.filter((ep) => {
    if (state.category !== "全部" && ep.category !== state.category) return false;
    if (!q) return true;
    const repText = (ep.repertoire || [])
      .map((t) => `${t.composer} ${t.piece} ${t.titleZh}`)
      .join(" ");
    const haystack = `${ep.id} ${ep.titleZh} ${ep.titleEn} ${ep.concepts} ${ep.thesis} ${ep.plain} ${repText}`.toLowerCase();
    return haystack.includes(q);
  });
}

function updateAudioButtons() {
  const { currentUrl, isPlaying } = state.audioState;
  document.querySelectorAll(".play-btn").forEach((btn) => {
    const match = btn.dataset.previewUrl === currentUrl && isPlaying;
    btn.setAttribute("aria-pressed", match ? "true" : "false");
    const span = btn.querySelector("span");
    if (span) span.textContent = match ? "暂停" : "试听";
    const svg = btn.querySelector("svg");
    if (svg) {
      svg.innerHTML = match
        ? '<rect x="2.5" y="2" width="2.4" height="8" rx="0.5"/><rect x="7.1" y="2" width="2.4" height="8" rx="0.5"/>'
        : '<path d="M3 2.2v7.6L9.8 6 3 2.2Z"/>';
    }
  });
  const dock = document.querySelector(".audio-dock");
  if (dock) {
    dock.outerHTML = renderAudioDock(state.audioState);
  }
}

function render(preserveSearchFocus = false) {
  document.body.setAttribute("data-proto", state.proto);
  const filtered = filterEpisodes();

  let mainHtml = "";
  if (state.proto === "a") {
    mainHtml = renderPrototypeA({
      episodes: filtered,
      category: state.category,
      query: state.query,
      showToolbar,
      audioState: state.audioState,
    });
  } else if (state.proto === "b") {
    mainHtml = renderPrototypeB({
      episodes: filtered,
      category: state.category,
      query: state.query,
      showToolbar,
      audioState: state.audioState,
    });
  } else {
    mainHtml = renderPrototypeC({
      episodes: filtered,
      allEpisodes: dataset.episodes,
      category: state.category,
      query: state.query,
      showToolbar,
      activeId: state.activeId,
      audioState: state.audioState,
    });
  }

  const appVersion = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "1.0.0";
  const footerHtml = `
      <footer class="site-footer">
        <span>讲稿依据 Leonard Bernstein 官方脚本 · 纽约爱乐档案核验</span>
        <span>v${appVersion} · B站 <a class="script-link" href="${dataset.bilibiliCollectionUrl}" target="_blank" rel="noopener">掘火档案（掘火中译）</a></span>
      </footer>
    `;

  app.innerHTML = `
    ${renderTopBar({
      proto: state.proto,
      collectionUrl: dataset.bilibiliCollectionUrl,
      totalCount: dataset.episodes.length,
    })}
    ${mainHtml}
    ${footerHtml}
    ${renderAudioDock(state.audioState)}
  `;

  if (preserveSearchFocus) {
    const input = app.querySelector(".search-input");
    if (input) {
      input.focus();
      const len = input.value.length;
      input.setSelectionRange(len, len);
    }
  }
}

app.addEventListener("click", (e) => {
  const protoBtn = e.target.closest("[data-set-proto]");
  if (protoBtn) {
    const next = protoBtn.dataset.setProto;
    if (next && next !== state.proto) {
      state.proto = next;
      history.replaceState(null, "", `#${next}`);
      window.scrollTo({ top: 0, behavior: "instant" });
      render();
    }
    return;
  }

  const catBtn = e.target.closest("[data-category]");
  if (catBtn) {
    state.category = catBtn.dataset.category;
    render();
    return;
  }

  const selectBtn = e.target.closest("[data-select-ep]");
  if (selectBtn && !selectBtn.disabled) {
    const nextId = Number(selectBtn.dataset.selectEp);
    if (nextId) {
      state.activeId = nextId;
      render();
      const stage = document.getElementById("proto-c-stage");
      if (stage && window.innerWidth <= 920) {
        stage.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
    return;
  }

  const playBtn = e.target.closest(".play-btn");
  if (playBtn) {
    togglePreview({
      previewUrl: playBtn.dataset.previewUrl,
      title: playBtn.dataset.trackTitle,
      artist: playBtn.dataset.trackArtist,
    });
    return;
  }

  if (e.target.closest("[data-dock-toggle]")) {
    togglePreview({
      previewUrl: state.audioState.currentUrl,
      title: state.audioState.title,
      artist: state.audioState.artist,
    });
    return;
  }

  if (e.target.closest("[data-dock-stop]")) {
    stopPreview();
  }
});

app.addEventListener("input", (e) => {
  if (e.target.classList.contains("search-input")) {
    state.query = e.target.value;
    render(true);
  }
});

window.addEventListener("hashchange", () => {
  const next = window.location.hash.replace("#", "").toLowerCase();
  if ((next === "a" || next === "b" || next === "c") && next !== state.proto) {
    state.proto = next;
    render();
  }
});

window.addEventListener("keydown", (e) => {
  if (state.proto !== "c") return;
  if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  const filtered = filterEpisodes();
  const idx = filtered.findIndex((ep) => ep.id === state.activeId);
  if (idx < 0) return;
  const nextIdx = e.key === "ArrowDown" ? idx + 1 : idx - 1;
  if (nextIdx >= 0 && nextIdx < filtered.length) {
    e.preventDefault();
    state.activeId = filtered[nextIdx].id;
    render();
  }
});

subscribeAudio((nextAudio) => {
  state.audioState = nextAudio;
  updateAudioButtons();
});

render();
