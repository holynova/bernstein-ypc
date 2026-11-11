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

if (fs.existsSync(distIndex)) {
  const html = fs.readFileSync(distIndex, "utf8");
  if (!html.includes('<div id="app"></div>')) {
    throw new Error("Built dist/index.html missing app mount point");
  }
}

console.log(
  `PASS (${raw.mode}): ${raw.episodes.length} episodes verified | ${biliCount} Bilibili 掘火中译 links | ${scriptCount} official scripts | ${trackCount} repertoire tracks (${previewCount} playable audio previews)`
);
