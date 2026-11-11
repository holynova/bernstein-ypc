import "./styles/base.css";
import "./styles/proto-c.css";

import dataset from "./data/episodes.json";
import slidesMap from "./data/slides.json";
import { getAudioState, stopPreview, subscribeAudio, togglePreview } from "./audio.js";
import {
  formatCountLabel,
  renderAudioDock,
  renderDirItems,
  renderPrototypeCShell,
  renderSlideViewerShell,
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
    dirList.innerHTML = renderDirItems(filtered, state.activeId, slidesMap);
    if (scrollDir) {
      const currentItem = dirList.querySelector('[aria-current="true"]');
      if (currentItem) currentItem.scrollIntoView({ block: "nearest" });
    }
  }

  const stage = document.getElementById("proto-c-stage");
  if (stage) {
    stage.innerHTML = renderStageContent(
      filtered,
      dataset.episodes,
      state.activeId,
      state.audioState,
      slidesMap
    );
    if (scrollStage && window.innerWidth <= 920) {
      stage.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
}

const SLIDE_PRELOAD_MAX = 45;
const slidePreloadMap = new Map();
const slideViewerState = {
  open: false,
  epId: null,
  page: 1,
  renderToken: 0,
  touchStartX: 0,
  touchStartY: 0,
};

function preloadSlideImg(url) {
  if (!url || slidePreloadMap.has(url)) return slidePreloadMap.get(url) || null;
  if (slidePreloadMap.size >= SLIDE_PRELOAD_MAX) {
    const oldestKey = slidePreloadMap.keys().next().value;
    slidePreloadMap.delete(oldestKey);
  }
  const im = new Image();
  im.decoding = "async";
  im.src = url;
  const ready =
    typeof im.decode === "function"
      ? im.decode().catch(() => {})
      : new Promise((resolve) => {
          if (im.complete) return resolve();
          im.onload = () => resolve();
          im.onerror = () => resolve();
        });
  slidePreloadMap.set(url, ready);
  return ready;
}

function getNextReadyEpisode(epId) {
  const idx = dataset.episodes.findIndex((e) => e.id === epId);
  for (let i = idx + 1; i < dataset.episodes.length; i++) {
    const cand = dataset.episodes[i];
    if (slidesMap[String(cand.id)]) return cand;
  }
  return null;
}

function syncSlideFullscreenLabel() {
  const viewer = document.getElementById("slide-viewer");
  const fsBtn = document.getElementById("slide-fs-btn");
  if (!viewer || !fsBtn) return;
  const isFs = Boolean(document.fullscreenElement === viewer || viewer.classList.contains("is-fullscreen"));
  fsBtn.textContent = isFs ? "退出全屏" : "全屏";
}

function toggleSlideFullscreen() {
  const viewer = document.getElementById("slide-viewer");
  if (!viewer) return;
  if (document.fullscreenElement === viewer) {
    document.exitFullscreen?.().catch(() => {});
    viewer.classList.remove("is-fullscreen");
    syncSlideFullscreenLabel();
    return;
  }
  if (viewer.classList.contains("is-fullscreen")) {
    viewer.classList.remove("is-fullscreen");
    syncSlideFullscreenLabel();
    return;
  }
  if (typeof viewer.requestFullscreen === "function") {
    viewer
      .requestFullscreen()
      .then(() => {
        viewer.classList.add("is-fullscreen");
        syncSlideFullscreenLabel();
      })
      .catch(() => {
        viewer.classList.add("is-fullscreen");
        syncSlideFullscreenLabel();
      });
  } else {
    viewer.classList.add("is-fullscreen");
    syncSlideFullscreenLabel();
  }
}

function showSlidePage(page) {
  const ep = dataset.episodes.find((e) => e.id === slideViewerState.epId);
  const meta = slidesMap[String(slideViewerState.epId)];
  const viewer = document.getElementById("slide-viewer");
  const img = document.getElementById("slide-img");
  const badge = document.getElementById("slide-page-badge");
  const endEl = document.getElementById("slide-end");
  const endTitle = document.getElementById("slide-end-title");
  const nextEpBtn = document.getElementById("slide-next-ep-btn");
  if (!ep || !meta || !viewer || !img || !badge || !endEl) return;

  const total = meta.pages;
  const clamped = Math.max(1, Math.min(page, total + 1));
  slideViewerState.page = clamped;

  if (clamped > total) {
    img.hidden = true;
    endEl.hidden = false;
    badge.textContent = `${total} / ${total}`;
    if (endTitle) endTitle.textContent = `第 ${ep.id} 集 · ${ep.titleZh}（共 ${total} 页）`;
    const nextReady = getNextReadyEpisode(ep.id);
    if (nextEpBtn) {
      if (nextReady) {
        nextEpBtn.hidden = false;
        nextEpBtn.dataset.slideNextEp = String(nextReady.id);
        nextEpBtn.textContent = `下一课图解：第 ${nextReady.id} 集 →`;
      } else {
        nextEpBtn.hidden = true;
      }
    }
    return;
  }

  endEl.hidden = true;
  img.hidden = false;
  badge.textContent = `${clamped} / ${total}`;
  img.alt = `第 ${ep.id} 集《${ep.titleZh}》图解幻灯片第 ${clamped} 页`;

  const url = `${meta.prefix}${clamped}.webp`;
  const token = ++slideViewerState.renderToken;
  const ready = preloadSlideImg(url);
  if (clamped + 1 <= total) preloadSlideImg(`${meta.prefix}${clamped + 1}.webp`);
  if (clamped + 2 <= total) preloadSlideImg(`${meta.prefix}${clamped + 2}.webp`);

  const applySrc = () => {
    if (token !== slideViewerState.renderToken) return;
    img.src = url;
  };
  if (ready && typeof ready.then === "function") {
    ready.then(applySrc);
  } else {
    applySrc();
  }
}

function openSlideViewer(epId, page = 1) {
  const ep = dataset.episodes.find((e) => e.id === epId);
  const meta = slidesMap[String(epId)];
  const viewer = document.getElementById("slide-viewer");
  if (!ep || !meta || !viewer) return;

  slideViewerState.open = true;
  slideViewerState.epId = epId;

  const titleEl = document.getElementById("slide-viewer-title");
  if (titleEl) titleEl.textContent = `第 ${ep.id} 集 · ${ep.titleZh}`;

  const pdfEl = document.getElementById("slide-pdf-link");
  if (pdfEl) {
    if (meta.pdfUrl) {
      pdfEl.href = meta.pdfUrl;
      pdfEl.download = `ep-${String(ep.id).padStart(2, "0")}.pdf`;
      pdfEl.hidden = false;
    } else {
      pdfEl.hidden = true;
    }
  }

  viewer.hidden = false;
  document.documentElement.classList.add("slide-viewer-open");
  showSlidePage(page);
}

function closeSlideViewer() {
  const viewer = document.getElementById("slide-viewer");
  if (!viewer) return;
  if (document.fullscreenElement === viewer) {
    document.exitFullscreen?.().catch(() => {});
  }
  viewer.classList.remove("is-fullscreen");
  syncSlideFullscreenLabel();
  viewer.hidden = true;
  document.documentElement.classList.remove("slide-viewer-open");
  slideViewerState.open = false;
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
      slidesMap,
    })}
    <footer class="site-footer">
      <span>讲稿依据 Leonard Bernstein 官方脚本 · 纽约爱乐档案核验</span>
      <span>${appVersion} · B站 <a class="script-link" href="${dataset.bilibiliCollectionUrl}" target="_blank" rel="noopener">掘火档案（掘火中译）</a></span>
    </footer>
    ${renderAudioDock(state.audioState)}
    ${renderSlideViewerShell()}
  `;

  const canvas = document.getElementById("slide-canvas");
  if (canvas) {
    canvas.addEventListener(
      "touchstart",
      (e) => {
        if (e.touches.length !== 1) return;
        slideViewerState.touchStartX = e.touches[0].clientX;
        slideViewerState.touchStartY = e.touches[0].clientY;
      },
      { passive: true }
    );
    canvas.addEventListener(
      "touchend",
      (e) => {
        if (!slideViewerState.open || e.changedTouches.length !== 1) return;
        const dx = e.changedTouches[0].clientX - slideViewerState.touchStartX;
        const dy = e.changedTouches[0].clientY - slideViewerState.touchStartY;
        if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) {
          showSlidePage(slideViewerState.page + (dx < 0 ? 1 : -1));
        }
      },
      { passive: true }
    );
  }
}

app.addEventListener("click", (e) => {
  const openSlideBtn = e.target.closest("[data-open-slides]");
  if (openSlideBtn) {
    const epId = Number(openSlideBtn.dataset.openSlides);
    const page = Number(openSlideBtn.dataset.slidePage || 1);
    if (epId) openSlideViewer(epId, page);
    return;
  }

  if (e.target.closest("[data-slide-close]")) {
    closeSlideViewer();
    return;
  }

  if (e.target.closest("[data-slide-fs]")) {
    toggleSlideFullscreen();
    return;
  }

  const slideDirBtn = e.target.closest("[data-slide-dir]");
  if (slideDirBtn && slideViewerState.open) {
    const dir = Number(slideDirBtn.dataset.slideDir);
    if (dir) showSlidePage(slideViewerState.page + dir);
    return;
  }

  if (e.target.closest("[data-slide-restart]") && slideViewerState.open) {
    showSlidePage(1);
    return;
  }

  const slideNextEpBtn = e.target.closest("[data-slide-next-ep]");
  if (slideNextEpBtn) {
    const nextId = Number(slideNextEpBtn.dataset.slideNextEp);
    if (nextId) {
      state.activeId = nextId;
      history.replaceState(null, "", `#ep-${nextId}`);
      syncView({ scrollStage: true, scrollDir: true });
      openSlideViewer(nextId, 1);
    }
    return;
  }

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

document.addEventListener("fullscreenchange", syncSlideFullscreenLabel);

window.addEventListener("keydown", (e) => {
  if (slideViewerState.open) {
    const viewer = document.getElementById("slide-viewer");
    if (e.key === "Escape") {
      e.preventDefault();
      if (viewer && (document.fullscreenElement === viewer || viewer.classList.contains("is-fullscreen"))) {
        toggleSlideFullscreen();
      } else {
        closeSlideViewer();
      }
      return;
    }
    if (e.key === "ArrowLeft" || e.key === "PageUp") {
      e.preventDefault();
      showSlidePage(slideViewerState.page - 1);
      return;
    }
    if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
      e.preventDefault();
      showSlidePage(slideViewerState.page + 1);
      return;
    }
    if (e.key === "Home") {
      e.preventDefault();
      showSlidePage(1);
      return;
    }
    if (e.key === "End") {
      e.preventDefault();
      const meta = slidesMap[String(slideViewerState.epId)];
      if (meta) showSlidePage(meta.pages);
      return;
    }
    if (e.key.toLowerCase() === "f" && !e.metaKey && !e.ctrlKey) {
      e.preventDefault();
      toggleSlideFullscreen();
    }
    return;
  }

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
