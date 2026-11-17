#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const episodesPath = path.join(root, "src/data/episodes.json");
const indexOutPath = path.join(root, "src/data/index.json");
const epRootDir = path.join(root, "public/ep");

const raw = fs.readFileSync(episodesPath, "utf8");
const data = JSON.parse(raw);
const epHash = crypto.createHash("sha256").update(raw).digest("hex").slice(0, 8);

const indexPayload = {
  bilibiliCollectionUrl: data.bilibiliCollectionUrl,
  epHash,
  totalEpisodes: data.totalEpisodes,
  episodes: data.episodes.map((ep) => ({
    id: ep.id,
    titleZh: ep.titleZh,
    titleEn: ep.titleEn,
    date: ep.date,
    dateZh: ep.dateZh,
    category: ep.category,
    hasBilibili: Boolean(ep.bilibili),
  })),
};

const indexText = JSON.stringify(indexPayload) + "\n";
if (!fs.existsSync(indexOutPath) || fs.readFileSync(indexOutPath, "utf8") !== indexText) {
  fs.writeFileSync(indexOutPath, indexText, "utf8");
}

fs.rmSync(epRootDir, { recursive: true, force: true });

console.log(`Prepared index (${data.episodes.length} episodes; full bundle via Vite chunk)`);
