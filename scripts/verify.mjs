import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const dataPath = path.join(root, "src/data/episodes.json");
const distIndex = path.join(root, "dist/index.html");

const raw = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const expectedMin = raw.mode === "sample" ? 3 : 53;

if (raw.episodes.length < expectedMin) {
  throw new Error(`Expected at least ${expectedMin} episodes, got ${raw.episodes.length}`);
}

let biliCount = 0;
let scriptCount = 0;
let trackCount = 0;
let previewCount = 0;

for (const ep of raw.episodes) {
  if (!ep.titleZh || !ep.titleEn || !ep.date || !ep.thesis || !ep.plain) {
    throw new Error(`Missing core field in episode ${ep.id}`);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(ep.date)) {
    throw new Error(`Invalid date format in episode ${ep.id}: ${ep.date}`);
  }
  const textFields = [ep.concepts, ep.thesis, ep.plain, ...(ep.scenes || [])];
  if (textFields.some((s) => /\*\*/.test(String(s || "")))) {
    throw new Error(`Raw markdown ** marker leaked in episode ${ep.id}`);
  }
  if (ep.bilibili) {
    biliCount++;
    if (!/^https:\/\/www\.bilibili\.com\/video\/BV[0-9A-Za-z]+$/.test(ep.bilibili.url)) {
      throw new Error(`Invalid Bilibili URL in episode ${ep.id}: ${ep.bilibili.url}`);
    }
  } else if (!ep.bilibiliSearchUrl) {
    throw new Error(`Missing fallback Bilibili search URL in episode ${ep.id}`);
  }
  if (ep.scriptUrl) scriptCount++;
  for (const t of ep.repertoire || []) {
    trackCount++;
    if (!t.composer || !t.piece) {
      throw new Error(`Invalid track in episode ${ep.id}`);
    }
    if (t.previewUrl) previewCount++;
  }
}

const renderSrc = fs.readFileSync(path.join(root, "src/render.js"), "utf8");
if (/<details[^>]*class="rep-details"[^>]*open/i.test(renderSrc)) {
  throw new Error("Repertoire details must be collapsed by default!");
}

const slidesPath = path.join(root, "src/data/slides.json");
const slidesMap = fs.existsSync(slidesPath) ? JSON.parse(fs.readFileSync(slidesPath, "utf8")) : {};
let slideDeckCount = 0;
let slidePageCount = 0;

for (const [epKey, meta] of Object.entries(slidesMap)) {
  if (!/^\d+$/.test(epKey) || !meta || typeof meta.pages !== "number" || meta.pages < 1) {
    throw new Error(`Invalid slide metadata for episode ${epKey}`);
  }
  const m = String(meta.prefix || "").match(/^\/bernstein-ypc\/static\/([0-9a-f]{16})\/$/);
  if (!m) {
    throw new Error(`Invalid slide static prefix for episode ${epKey}: ${meta.prefix}`);
  }
  const staticDir = path.join(root, "public/static", m[1]);
  for (let p = 1; p <= meta.pages; p++) {
    const webp = path.join(staticDir, `${p}.webp`);
    if (!fs.existsSync(webp) || fs.statSync(webp).size < 1000) {
      throw new Error(`Missing or empty slide WebP: ${webp}`);
    }
  }
  if (meta.pdfUrl) {
    const pdfRel = String(meta.pdfUrl).replace(/^\/bernstein-ypc\//, "");
    const pdfDisk = path.join(root, "public", pdfRel);
    if (!fs.existsSync(pdfDisk) || fs.statSync(pdfDisk).size < 1024) {
      throw new Error(`Missing or empty downloadable PDF: ${pdfDisk}`);
    }
  }
  slideDeckCount++;
  slidePageCount += meta.pages;
}

if (fs.existsSync(distIndex)) {
  const html = fs.readFileSync(distIndex, "utf8");
  if (!html.includes('<div id="app"></div>')) {
    throw new Error("Built dist/index.html missing app mount point");
  }
  const distDir = path.join(root, "dist");
  for (const forbidden of ["work", "state", "logs", "sources"]) {
    if (fs.existsSync(path.join(distDir, forbidden))) {
      throw new Error(`Forbidden internal directory leaked into dist/: ${forbidden}`);
    }
  }
}

console.log(
  `PASS (${raw.mode}): ${raw.episodes.length} episodes verified | ${biliCount} Bilibili 掘火中译 links | ${scriptCount} official scripts | ${trackCount} repertoire tracks (${previewCount} playable audio previews) | ${slideDeckCount} PPT slide decks (${slidePageCount} WebP pages)`
);
