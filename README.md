# Bernstein's Young People's Concerts / 伯恩斯坦《青少年音乐会》

中文：整理伦纳德·伯恩斯坦《青少年音乐会》（1958–1972）全部 53 课核心观点、通俗讲解与现场演奏例子，采用双栏目录精读界面，支持课程搜索与分类筛选，附带 B 站“掘火中译”视频与可折叠试听曲目单。

English: An archival two-column study guide to all 53 episodes of Leonard Bernstein's *Young People's Concerts* (1958–1972), featuring live search, category filtering, verified takeaways, stage demonstrations, Bilibili Chinese-subtitled video links, and collapsible track previews.

![Project screenshot](./assets/screenshot.png)

## 在线体验 / Live Demo

- [Cloudflare Demo](https://xiaosang.cc/bernstein-ypc/)
- [GitHub Repo](https://github.com/holynova/bernstein-ypc)

<img src="./assets/qr.png" width="180" alt="扫码访问 Cloudflare 在线体验">

## 本地运行 / Run locally

```bash
npm install
npm run dev
```

## 发布 / Deploy

```bash
npm run deploy
```

Cloudflare Workers · Subpath Route: `xiaosang.cc/bernstein-ypc/*`

源码与部署配置使用同一个 `main` 主分支；在本地手动构建并部署，不创建 Cloudflare 专用分支或 GitHub Action。
