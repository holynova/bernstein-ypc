import "./styles/base.css";
import "./styles/proto-c.css";

import dataset from "./data/episodes.json";
import { getAudioState, stopPreview, subscribeAudio, togglePreview } from "./audio.js";
import {
  formatCountLabel,
  renderAudioDock,
  renderDirItems,
  renderPrototypeCShell,
  renderStageContent,
  renderTopBar,
} from "./render.js";

function readInitialEpId() {
  const params = new URLSearchParams(window.location.search);
  const qp = Number(params.get("ep"));
  if (qp && dataset.episodes.some((e) => e.id === qp)) return qp;
  const match = window.location.hash.match(/^#ep-(\d+)$/i);
  if (match) {
    const id = Number(match[1]);
    if (dataset.episodes.some((e) => e.id === id)) return id;
  }
  return dataset.episodes[0]?.id ?? 1;
}

const state = {
  category: "全部",
  query: "",
  isComposing: false,
  activeId: readInitialEpId(),
  audioState: getAudioState(),
};

const app = document.getElementById("app");
const indexedText = new Map(
  dataset.episodes.map((ep) => {
    const repText = (ep.repertoire || [])
      .map((t) => `${t.composer} ${t.piece} ${t.titleZh} ${t.recordingArtist || ""}`)
      .join(" ");
    const blob = [
      ep.id,
      `第${ep.id}集`,
      ep.date,
      ep.titleZh,
      ep.titleEn,
      ep.category,
      ep.concepts,
      ep.thesis,
      ep.plain,
      ...(ep.scenes || []),
      repText,
    ]
      .join(" ")
      .toLowerCase();
    return [ep.id, blob];
  })
);

function filterEpisodes() {
  const terms = state.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return dataset.episodes.filter((ep) => {
    if (state.category !== "全部" && ep.category !== state.category) return false;
    if (!terms.length) return true;
    const blob = indexedText.get(ep.id) || "";
    return terms.every((t) => blob.includes(t));
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

function syncView({ scrollStage = false, scrollDir = false } = {}) {
  const filtered = filterEpisodes();
  if (filtered.length && !filtered.some((e) => e.id === state.activeId)) {
    state.activeId = filtered[0].id;
  }

  const countEl = document.getElementById("site-count");
  if (countEl) {
    countEl.textContent = formatCountLabel(filtered.length, dataset.episodes.length);
  }

  const clearBtn = app.querySelector("[data-clear-search]");
  if (clearBtn) {
    clearBtn.hidden = !state.query;
  }

  app.querySelectorAll("[data-category]").forEach((btn) => {
    btn.setAttribute("aria-pressed", btn.dataset.category === state.category ? "true" : "false");
  });

  const dirList = document.getElementById("proto-c-dir-list");
  if (dirList) {
    dirList.innerHTML = renderDirItems(filtered, state.activeId);
    if (scrollDir) {
      const currentItem = dirList.querySelector('[aria-current="true"]');
      if (currentItem) currentItem.scrollIntoView({ block: "nearest" });
    }
  }

  const stage = document.getElementById("proto-c-stage");
  if (stage) {
    stage.innerHTML = renderStageContent(filtered, dataset.episodes, state.activeId, state.audioState);
    if (scrollStage && window.innerWidth <= 920) {
      stage.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
}

function mountApp() {
  document.body.setAttribute("data-proto", "c");
  const filtered = filterEpisodes();
  const appVersion = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "v1.0.1";

  app.innerHTML = `
    ${renderTopBar({
      collectionUrl: dataset.bilibiliCollectionUrl,
      visibleCount: filtered.length,
      totalCount: dataset.episodes.length,
    })}
    ${renderPrototypeCShell({
      episodes: filtered,
      allEpisodes: dataset.episodes,
      category: state.category,
      query: state.query,
      activeId: state.activeId,
      audioState: state.audioState,
    })}
    <footer class="site-footer">
      <span>讲稿依据 Leonard Bernstein 官方脚本 · 纽约爱乐档案核验</span>
      <span>${appVersion} · B站 <a class="script-link" href="${dataset.bilibiliCollectionUrl}" target="_blank" rel="noopener">掘火档案（掘火中译）</a></span>
    </footer>
    ${renderAudioDock(state.audioState)}
  `;
}

app.addEventListener("click", (e) => {
  const catBtn = e.target.closest("[data-category]");
  if (catBtn) {
    state.category = catBtn.dataset.category;
    syncView();
    return;
  }

  if (e.target.closest("[data-clear-search]")) {
    state.query = "";
    const input = app.querySelector(".search-input");
    if (input) {
      input.value = "";
      input.focus();
    }
    syncView();
    return;
  }

  const selectBtn = e.target.closest("[data-select-ep]");
  if (selectBtn && !selectBtn.disabled) {
    const nextId = Number(selectBtn.dataset.selectEp);
    if (nextId) {
      state.activeId = nextId;
      history.replaceState(null, "", `#ep-${nextId}`);
      syncView({ scrollStage: true, scrollDir: true });
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

app.addEventListener("compositionstart", (e) => {
  if (e.target.classList.contains("search-input")) {
    state.isComposing = true;
  }
});

app.addEventListener("compositionend", (e) => {
  if (e.target.classList.contains("search-input")) {
    state.isComposing = false;
    state.query = e.target.value;
    syncView();
  }
});

app.addEventListener("input", (e) => {
  if (e.target.classList.contains("search-input") && !state.isComposing) {
    state.query = e.target.value;
    syncView();
  }
});

window.addEventListener("hashchange", () => {
  const match = window.location.hash.match(/^#ep-(\d+)$/i);
  if (match) {
    const id = Number(match[1]);
    if (dataset.episodes.some((ep) => ep.id === id) && id !== state.activeId) {
      state.activeId = id;
      syncView({ scrollDir: true });
    }
  }
});

window.addEventListener("keydown", (e) => {
  const inInput = e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA");
  if (e.key === "/" && !inInput && !e.metaKey && !e.ctrlKey) {
    const input = app.querySelector(".search-input");
    if (input) {
      e.preventDefault();
      input.focus();
      input.select();
    }
    return;
  }
  if (e.key === "Escape" && state.query) {
    state.query = "";
    const input = app.querySelector(".search-input");
    if (input) input.value = "";
    syncView();
    return;
  }
  if (inInput) return;
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  const filtered = filterEpisodes();
  const idx = filtered.findIndex((ep) => ep.id === state.activeId);
  if (idx < 0) return;
  const nextIdx = e.key === "ArrowDown" ? idx + 1 : idx - 1;
  if (nextIdx >= 0 && nextIdx < filtered.length) {
    e.preventDefault();
    state.activeId = filtered[nextIdx].id;
    history.replaceState(null, "", `#ep-${state.activeId}`);
    syncView({ scrollDir: true });
  }
});

subscribeAudio((nextAudio) => {
  state.audioState = nextAudio;
  updateAudioButtons();
});

mountApp();
