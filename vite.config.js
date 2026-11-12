import { defineConfig } from "vite";
import fs from "node:fs";
import path from "node:path";

const pkg = JSON.parse(fs.readFileSync(new URL("./package.json", import.meta.url), "utf8"));

function bernsteinPreloadPlugin() {
  return {
    name: "bernstein-lcp-preload",
    transformIndexHtml(html) {
      const idxPath = path.resolve(import.meta.dirname, "src/data/index.json");
      const slidesPath = path.resolve(import.meta.dirname, "src/data/slides.json");
      const idxData = JSON.parse(fs.readFileSync(idxPath, "utf8"));
      const slidesData = JSON.parse(fs.readFileSync(slidesPath, "utf8"));
      const slideHashes = {};
      for (const [epId, meta] of Object.entries(slidesData)) {
        const m = /\/static\/([^/]+)\/$/.exec(meta.prefix || "");
        if (m) slideHashes[epId] = m[1];
      }
      const total = Number(idxData.totalEpisodes || idxData.episodes?.length || 53);
      const inlineScript = `<script>!function(){var h=${JSON.stringify(idxData.epHash)},s=${JSON.stringify(slideHashes)},q=/[?&]ep=(\\d+)/i.exec(location.search),m=/^#ep-(\\d+)$/i.exec(location.hash),n=Number((q&&q[1])||(m&&m[1])||0),id=n>=1&&n<=${total}?String(n):"1",b="/bernstein-ypc/";window.__EP_ID__=id;window.__EP_PRELOAD__=fetch(b+"ep/"+h+"/"+id+".json",{priority:"high"}).then(function(r){return r.ok?r.json():null}).catch(function(){return null});if(s[id]){var l=document.createElement("link");l.rel="preload";l.as="image";l.href=b+"static/"+s[id]+"/1.webp";l.fetchPriority="high";document.head.appendChild(l);}}();</script>`;
      return html.replace("<!--__LCP_PRELOAD__-->", inlineScript);
    },
  };
}

export default defineConfig({
  base: "/bernstein-ypc/",
  plugins: [bernsteinPreloadPlugin()],
  define: {
    __APP_VERSION__: JSON.stringify(`v${pkg.version}`),
  },
});
