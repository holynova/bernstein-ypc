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

export function renderTopBar({ proto, collectionUrl, totalCount }) {
  const buttons = [
    { id: "a", label: "原型 A · 节目单列表" },
    { id: "b", label: "原型 B · 音乐厅卡片" },
    { id: "c", label: "原型 C · 双栏精读" },
  ];
  return `
    <header class="proto-bar">
      <div class="proto-bar-inner">
        <div class="brand-group">
          <h1 class="site-title">伯恩斯坦《青少年音乐会》</h1>
          <span class="site-years tabular-nums">${totalCount} 课</span>
          <a class="script-link" href="${esc(collectionUrl)}" target="_blank" rel="noopener">掘火中译合集 ↗</a>
          <a class="script-link" href="https://github.com/holynova/bernstein-ypc" target="_blank" rel="noopener">GitHub ↗</a>
        </div>
        <nav class="proto-switcher" aria-label="原型对比">
          ${buttons
            .map(
              (b) => `<button type="button" class="proto-btn" data-set-proto="${b.id}" aria-pressed="${
                proto === b.id ? "true" : "false"
              }">${esc(b.label)}</button>`
            )
            .join("")}
        </nav>
      </div>
    </header>
  `;
}

export function renderToolbar({ category, query, showToolbar }) {
  if (!showToolbar) return "";
  return `
    <div class="toolbar">
      <div class="filter-pills" role="group" aria-label="课程分类">
        ${CATEGORIES.map(
          (c) => `<button type="button" class="filter-pill" data-category="${esc(c)}" aria-pressed="${
            category === c ? "true" : "false"
          }">${esc(c)}</button>`
        ).join("")}
      </div>
      <div class="search-wrap">
        ${ICONS.search}
        <input
          type="search"
          class="search-input"
          value="${esc(query)}"
          placeholder="搜索课程、作曲家、曲目…"
          aria-label="搜索课程、作曲家或曲目"
        />
      </div>
    </div>
  `;
}

function renderActionLinks(ep) {
  const bili = ep.bilibili
    ? `<a class="bili-link" href="${esc(ep.bilibili.url)}" target="_blank" rel="noopener" title="${esc(
        ep.bilibili.title
      )}">掘火中译 · ${esc(ep.bilibili.duration)} ↗</a>`
    : `<a class="bili-link is-search" href="${esc(ep.bilibiliSearchUrl)}" target="_blank" rel="noopener">B站检索 ↗</a>`;

  const script = ep.scriptUrl
    ? `<a class="script-link" href="${esc(ep.scriptUrl)}" target="_blank" rel="noopener">英文讲稿 ↗</a>`
    : "";

  return `<div class="ep-links">${bili}${script}</div>`;
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

export function renderPrototypeA({ episodes, category, query, showToolbar, audioState }) {
  const rows = episodes.length
    ? episodes
        .map(
          (ep) => `
        <article class="ledger-row" id="ep-${ep.id}">
          <div class="ledger-rail">
            <span class="ledger-num">${String(ep.id).padStart(2, "0")}</span>
            <time class="ledger-date" datetime="${esc(ep.date)}">${esc(ep.date)}</time>
          </div>
          <div class="ledger-content">
            <div class="ledger-head">
              <div class="ledger-titles">
                <h2 class="ledger-title-zh">${esc(ep.titleZh)}</h2>
                <span class="ledger-title-en">${esc(ep.titleEn)}</span>
              </div>
              ${renderActionLinks(ep)}
            </div>
            ${renderLessonBody(ep)}
            ${renderRepertoire(ep, audioState)}
          </div>
        </article>
      `
        )
        .join("")
    : `<div class="empty-state">没有匹配的课程</div>`;

  return `
    <main class="proto-a-main">
      ${showToolbar ? `<div class="proto-a-head">${renderToolbar({ category, query, showToolbar })}</div>` : ""}
      <div class="proto-a-list">${rows}</div>
    </main>
  `;
}

export function renderPrototypeB({ episodes, category, query, showToolbar, audioState }) {
  const cards = episodes.length
    ? episodes
        .map(
          (ep) => `
        <article class="stage-card" id="ep-${ep.id}">
          <div class="stage-card-top">
            <div class="stage-card-meta">
              <span class="stage-card-num">${String(ep.id).padStart(2, "0")}</span>
              <time datetime="${esc(ep.date)}">${esc(ep.date)}</time>
            </div>
            ${renderActionLinks(ep)}
          </div>
          <div class="stage-card-titles">
            <h2 class="stage-card-title-zh">${esc(ep.titleZh)}</h2>
            <span class="stage-card-title-en">${esc(ep.titleEn)}</span>
          </div>
          ${renderLessonBody(ep)}
          <div class="stage-card-footer">
            ${renderRepertoire(ep, audioState)}
          </div>
        </article>
      `
        )
        .join("")
    : `<div class="empty-state">没有匹配的课程</div>`;

  return `
    <main class="proto-b-main">
      ${showToolbar ? `<div class="proto-b-head">${renderToolbar({ category, query, showToolbar })}</div>` : ""}
      <div class="proto-b-grid">${cards}</div>
    </main>
  `;
}

export function renderPrototypeC({
  episodes,
  allEpisodes,
  category,
  query,
  showToolbar,
  activeId,
  audioState,
}) {
  const active = episodes.find((e) => e.id === activeId) || episodes[0] || allEpisodes[0];
  const activeIdx = episodes.findIndex((e) => e.id === active?.id);
  const prevEp = activeIdx > 0 ? episodes[activeIdx - 1] : null;
  const nextEp = activeIdx >= 0 && activeIdx < episodes.length - 1 ? episodes[activeIdx + 1] : null;

  return `
    <div class="proto-c-shell">
      <aside class="proto-c-sidebar" aria-label="课程目录">
        ${
          showToolbar
            ? `<div class="proto-c-side-controls">${renderToolbar({ category, query, showToolbar })}</div>`
            : ""
        }
        <ul class="proto-c-dir-list">
          ${
            episodes.length
              ? episodes
                  .map(
                    (ep) => `
                <li>
                  <button
                    type="button"
                    class="dir-btn"
                    data-select-ep="${ep.id}"
                    aria-current="${ep.id === active?.id ? "true" : "false"}"
                  >
                    <span class="dir-num">${String(ep.id).padStart(2, "0")}</span>
                    <span class="dir-title">${esc(ep.titleZh)}</span>
                    <span class="dir-year">${esc(ep.date.slice(0, 4))}</span>
                  </button>
                </li>
              `
                  )
                  .join("")
              : `<li class="empty-state">无匹配课程</li>`
          }
        </ul>
      </aside>
      <main class="proto-c-stage" id="proto-c-stage">
        ${
          active
            ? `
          <div class="stage-top-row">
            <div class="stage-date-num">
              <span class="stage-big-num">第 ${active.id} 集</span>
              <time datetime="${esc(active.date)}">${esc(active.dateZh)}</time>
            </div>
            ${renderActionLinks(active)}
          </div>
          <h2 class="stage-title-zh">${esc(active.titleZh)}</h2>
          <p class="stage-title-en">${esc(active.titleEn)}</p>
          ${renderLessonBody(active)}
          ${renderRepertoire(active, audioState)}
          <div class="stage-nav">
            <button type="button" class="stage-nav-btn" data-select-ep="${prevEp ? prevEp.id : ""}" ${
              prevEp ? "" : "disabled"
            }>← ${prevEp ? `第 ${prevEp.id} 集 · ${esc(prevEp.titleZh)}` : "已至首课"}</button>
            <button type="button" class="stage-nav-btn" data-select-ep="${nextEp ? nextEp.id : ""}" ${
              nextEp ? "" : "disabled"
            }>${nextEp ? `第 ${nextEp.id} 集 · ${esc(nextEp.titleZh)}` : "已至末课"} →</button>
          </div>
        `
            : `<div class="empty-state">没有匹配的课程</div>`
        }
      </main>
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
