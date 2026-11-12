const CATEGORIES = ["全部", "基础乐理", "大师与杰作", "文化与跨界", "青年专场"];

export function esc(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const ICONS = {
  search: `<svg class="search-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14" stroke-linecap="round"/></svg>`,
  chevron: `<svg class="rep-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="m6 3.5 4.5 4.5L6 12.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  play: `<svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true"><path d="M3 2.2v7.6L9.8 6 3 2.2Z"/></svg>`,
  pause: `<svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true"><rect x="2.5" y="2" width="2.4" height="8" rx="0.5"/><rect x="7.1" y="2" width="2.4" height="8" rx="0.5"/></svg>`,
};

export function formatCountLabel(visibleCount, totalCount) {
  return visibleCount === totalCount ? `${totalCount} 课` : `${visibleCount} / ${totalCount} 课`;
}

export function renderTopBar({ collectionUrl, visibleCount, totalCount }) {
  return `
    <header class="proto-bar">
      <div class="proto-bar-inner">
        <div class="brand-group">
          <h1 class="site-title">伯恩斯坦《青少年音乐会》</h1>
          <span class="site-years tabular-nums" id="site-count">${formatCountLabel(visibleCount, totalCount)}</span>
        </div>
        <nav class="header-links" aria-label="外部链接">
          <a class="script-link" href="${esc(collectionUrl)}" target="_blank" rel="noopener">掘火中译合集 ↗</a>
          <a class="script-link" href="https://github.com/holynova/bernstein-ypc" target="_blank" rel="noopener">GitHub ↗</a>
        </nav>
      </div>
    </header>
  `;
}

export function renderSidebarToolbar({ category, query }) {
  return `
    <div class="proto-c-side-controls">
      <div class="search-wrap">
        ${ICONS.search}
        <input
          type="search"
          class="search-input"
          value="${esc(query)}"
          placeholder="搜索课题、作曲家、曲目… ( / )"
          aria-label="搜索课程、作曲家、曲目或概念"
          autocomplete="off"
        />
        <button
          type="button"
          class="search-clear"
          data-clear-search
          aria-label="清空搜索"
          ${query ? "" : "hidden"}
        >×</button>
      </div>
      <div class="filter-pills" role="group" aria-label="课程分类">
        ${CATEGORIES.map(
          (c) => `<button type="button" class="filter-pill" data-category="${esc(c)}" aria-pressed="${
            category === c ? "true" : "false"
          }">${esc(c)}</button>`
        ).join("")}
      </div>
    </div>
  `;
}

export function renderActionLinks(ep, slide) {
  const slidesBtn = slide
    ? `<button type="button" class="slide-trigger-btn" data-open-slides="${ep.id}" data-slide-page="1">图解 PPT · ${slide.pages} 页</button>`
    : "";

  const bili = ep.bilibili
    ? `<a class="bili-link" href="${esc(ep.bilibili.url)}" target="_blank" rel="noopener" title="${esc(
        ep.bilibili.title
      )}">掘火中译 · ${esc(ep.bilibili.duration)} ↗</a>`
    : ep.bilibiliSearchUrl
    ? `<a class="bili-link is-search" href="${esc(ep.bilibiliSearchUrl)}" target="_blank" rel="noopener">B站检索 ↗</a>`
    : "";

  const script = ep.scriptUrl
    ? `<a class="script-link" href="${esc(ep.scriptUrl)}" target="_blank" rel="noopener">英文讲稿 ↗</a>`
    : "";

  return `<div class="ep-links" data-stage-links>${slidesBtn}${bili}${script}</div>`;
}

function renderSlideStrip(ep, slide) {
  if (!slide || !slide.prefix || !slide.pages) return "";
  const coverSrc = `${slide.prefix}1.webp`;
  return `
    <section class="slide-strip" aria-label="课程图解幻灯片">
      <button
        type="button"
        class="slide-cover-btn"
        data-open-slides="${ep.id}"
        data-slide-page="1"
        aria-label="全屏阅读第 ${ep.id} 集图解幻灯片（共 ${slide.pages} 页）"
      >
        <img
          class="slide-cover-img"
          src="${esc(coverSrc)}"
          width="1376"
          height="768"
          alt="第 ${ep.id} 集《${esc(ep.titleZh)}》图解幻灯片第 1 页"
          fetchpriority="high"
          decoding="async"
        />
        <span class="slide-cover-badge tabular-nums">1 / ${slide.pages} · 全屏</span>
      </button>
    </section>
  `;
}

function renderRepertoire(ep, audioState) {
  const tracks = ep.repertoire || [];
  if (!tracks.length) return "";
  return `
    <details class="rep-details">
      <summary class="rep-summary">
        ${ICONS.chevron}
        <span>曲目 · ${tracks.length} 首</span>
      </summary>
      <ul class="rep-list">
        ${tracks
          .map((t) => {
            const isPlaying =
              audioState.currentUrl &&
              audioState.currentUrl === t.previewUrl &&
              audioState.isPlaying;
            const playBtn = t.previewUrl
              ? `<button
                  type="button"
                  class="play-btn"
                  data-preview-url="${esc(t.previewUrl)}"
                  data-track-title="${esc(t.titleZh || t.piece)}"
                  data-track-artist="${esc(t.recordingArtist || t.composer)}"
                  aria-pressed="${isPlaying ? "true" : "false"}"
                >${isPlaying ? ICONS.pause : ICONS.play}<span>${isPlaying ? "暂停" : "试听"}</span></button>`
              : "";
            const extLink = t.appleMusicUrl
              ? `<a class="track-ext-link" href="${esc(t.appleMusicUrl)}" target="_blank" rel="noopener">Apple Music</a>`
              : `<a class="track-ext-link" href="${esc(t.youtubeSearchUrl)}" target="_blank" rel="noopener">YouTube</a>`;
            const biliTrack = `<a class="track-ext-link" href="${esc(t.biliSearchUrl)}" target="_blank" rel="noopener">B站</a>`;
            return `
              <li class="rep-item">
                <div class="rep-info">
                  <span class="rep-composer">${esc(t.composer)}</span>
                  <span class="rep-piece">${esc(t.titleZh)} · ${esc(t.piece)}</span>
                </div>
                <div class="rep-actions">
                  ${playBtn}
                  ${extLink}
                  ${biliTrack}
                </div>
              </li>
            `;
          })
          .join("")}
      </ul>
    </details>
  `;
}

function renderLessonBody(ep) {
  if (!ep.thesis && !ep.plain) {
    return `<p class="ep-thesis" aria-busy="true">正在载入讲稿与曲目…</p>`;
  }
  return `
    <p class="ep-thesis">${esc(ep.thesis)}</p>
    <p class="ep-plain">${esc(ep.plain)}</p>
    ${
      ep.scenes && ep.scenes.length
        ? `<ul class="ep-scenes">${ep.scenes.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>`
        : ""
    }
    <div class="ep-concepts">${esc(ep.concepts)}</div>
  `;
}

export function renderStageDetail(ep, audioState) {
  return `${renderLessonBody(ep)}${renderRepertoire(ep, audioState)}`;
}

export function renderDirItems(episodes, activeId, slidesMap = {}) {
  if (!episodes.length) {
    return `<li class="empty-state">没有匹配的课程</li>`;
  }
  return episodes
    .map((ep) => {
      const hasSlides = Boolean(slidesMap[String(ep.id)]);
      const hasBilibili = Boolean(ep.hasBilibili ?? ep.bilibili);
      return `
      <li>
        <button
          type="button"
          class="dir-btn"
          data-select-ep="${ep.id}"
          aria-current="${ep.id === activeId ? "true" : "false"}"
        >
          <span class="dir-num">${String(ep.id).padStart(2, "0")}</span>
          <span class="dir-title">${esc(ep.titleZh)}</span>
          <span class="dir-meta">
            ${
              hasBilibili || hasSlides
                ? `<span class="dir-indicators" aria-hidden="true">
                    ${hasBilibili ? `<span class="dir-dot is-bili" title="含 B站掘火中译视频"></span>` : ""}
                    ${hasSlides ? `<span class="dir-dot is-slide" title="含图解 PPT"></span>` : ""}
                  </span>`
                : ""
            }
            <span class="dir-year">${esc(ep.date.slice(0, 4))}</span>
          </span>
        </button>
      </li>
    `;
    })
    .join("");
}

export function renderStageContent(episodes, allEpisodes, activeId, audioState, slidesMap = {}) {
  const active = episodes.find((e) => e.id === activeId) || episodes[0] || null;
  if (!active) {
    return `<div class="empty-state">没有找到符合条件的课程${
      allEpisodes.length ? "，请尝试换个关键词或切换分类。" : ""
    }</div>`;
  }
  const activeIdx = episodes.findIndex((e) => e.id === active.id);
  const prevEp = activeIdx > 0 ? episodes[activeIdx - 1] : null;
  const nextEp = activeIdx >= 0 && activeIdx < episodes.length - 1 ? episodes[activeIdx + 1] : null;
  const slide = slidesMap[String(active.id)] || null;

  return `
    <div class="stage-top-row">
      <div class="stage-date-num">
        <span class="stage-big-num">第 ${active.id} 集</span>
        <time datetime="${esc(active.date)}">${esc(active.dateZh)}</time>
      </div>
      ${renderActionLinks(active, slide)}
    </div>
    <h2 class="stage-title-zh">${esc(active.titleZh)}</h2>
    <p class="stage-title-en">${esc(active.titleEn)}</p>
    ${renderSlideStrip(active, slide)}
    <div class="stage-detail-body" data-stage-body>
      ${renderStageDetail(active, audioState)}
    </div>
    <div class="stage-nav">
      <button type="button" class="stage-nav-btn" data-select-ep="${prevEp ? prevEp.id : ""}" ${
        prevEp ? "" : "disabled"
      }>← ${prevEp ? `第 ${prevEp.id} 集 · ${esc(prevEp.titleZh)}` : "已至首课"}</button>
      <button type="button" class="stage-nav-btn" data-select-ep="${nextEp ? nextEp.id : ""}" ${
        nextEp ? "" : "disabled"
      }>${nextEp ? `第 ${nextEp.id} 集 · ${esc(nextEp.titleZh)}` : "已至末课"} →</button>
    </div>
  `;
}

export function renderPrototypeCShell({
  episodes,
  allEpisodes,
  category,
  query,
  activeId,
  audioState,
  slidesMap = {},
}) {
  return `
    <div class="proto-c-shell">
      <aside class="proto-c-sidebar" aria-label="课程目录与搜索">
        ${renderSidebarToolbar({ category, query })}
        <ul class="proto-c-dir-list" id="proto-c-dir-list">
          ${renderDirItems(episodes, activeId, slidesMap)}
        </ul>
      </aside>
      <main class="proto-c-stage" id="proto-c-stage">
        ${renderStageContent(episodes, allEpisodes, activeId, audioState, slidesMap)}
      </main>
    </div>
  `;
}

export function renderSlideViewerShell() {
  return `
    <div class="slide-viewer" id="slide-viewer" hidden role="dialog" aria-modal="true" aria-labelledby="slide-viewer-title">
      <div class="slide-viewer-bar">
        <div class="slide-viewer-title-wrap">
          <strong class="slide-viewer-title" id="slide-viewer-title"></strong>
        </div>
        <div class="slide-viewer-controls">
          <span class="slide-page-badge tabular-nums" id="slide-page-badge"></span>
          <button type="button" class="slide-bar-btn" id="slide-fs-btn" data-slide-fs aria-label="切换全屏">全屏</button>
          <button type="button" class="slide-bar-btn is-close" data-slide-close aria-label="关闭图解阅读器">关闭</button>
        </div>
      </div>
      <div class="slide-canvas" id="slide-canvas">
        <button type="button" class="slide-zone is-prev" data-slide-dir="-1" aria-label="上一页">
          <span class="slide-arrow" aria-hidden="true">‹</span>
        </button>
        <img id="slide-img" class="slide-img" width="1376" height="768" alt="" decoding="async" />
        <span class="slide-loading-pill" id="slide-loading-pill" hidden>加载中…</span>
        <button type="button" class="slide-zone is-next" data-slide-dir="1" aria-label="下一页">
          <span class="slide-arrow" aria-hidden="true">›</span>
        </button>
        <div class="slide-end" id="slide-end" hidden>
          <p class="slide-end-title" id="slide-end-title"></p>
          <div class="slide-end-actions">
            <button type="button" class="slide-bar-btn" data-slide-restart>再看一遍</button>
            <button type="button" class="slide-bar-btn is-primary" id="slide-next-ep-btn" data-slide-next-ep hidden></button>
            <button type="button" class="slide-bar-btn" data-slide-close>返回课文</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

export function renderAudioDock(audioState) {
  const hidden = !audioState.currentUrl;
  return `
    <div class="audio-dock" ${hidden ? "hidden" : ""} role="region" aria-label="曲目试听">
      <div class="audio-dock-meta">
        <div class="audio-dock-title">${esc(audioState.title)}</div>
        <div class="audio-dock-sub">${esc(audioState.artist)}</div>
      </div>
      <button type="button" class="audio-dock-btn" data-dock-toggle>
        ${audioState.isPlaying ? "暂停" : "继续"}
      </button>
      <button type="button" class="audio-dock-btn" data-dock-stop>关闭</button>
    </div>
  `;
}
