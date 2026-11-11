import { defineConfig } from "vite";
import fs from "node:fs";

const pkg = JSON.parse(fs.readFileSync(new URL("./package.json", import.meta.url), "utf8"));

export default defineConfig({
  base: "/bernstein-ypc/",
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
});
