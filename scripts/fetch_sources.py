#!/usr/bin/env python3
"""Fetch and clean all 53 Young People's Concerts sources into work/sources/."""

import hashlib
import html
import json
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
EPISODES_JSON = ROOT / "src/data/episodes.json"
SOURCES_DIR = ROOT / "work/sources"

YOUTUBE_NON_SCRIPT = {
    14: "https://www.youtube.com/watch?v=3FemcQeE2YI",
    19: "https://www.youtube.com/watch?v=4FTC0INmv0w",
    22: "https://www.youtube.com/watch?v=R9w1Sw9MxBU",
    25: "https://www.youtube.com/watch?v=53TbMRE3R94",
    30: "https://www.youtube.com/watch?v=ZS8pQm-6qsE",
    35: "https://www.youtube.com/watch?v=htaUgBMoVHQ",
    37: "https://www.youtube.com/watch?v=6D-f8wYTB7U",
    39: "https://www.youtube.com/watch?v=AAHMCT5Akyc",
    42: "https://www.youtube.com/watch?v=bbNPhhIafQk",
}


def fetch_official_script(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw_html = resp.read().decode("utf-8", errors="replace")

    paragraphs = []
    for chunk in re.findall(r"<p[^>]*>([\s\S]*?)</p>", raw_html, re.IGNORECASE):
        text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", chunk))).strip()
        if not text:
            continue
        if text.startswith("©") and "Amberson Holdings" in text:
            break
        if text.startswith("Watch a video excerpt"):
            break
        paragraphs.append(text)

    if len(paragraphs) < 5:
        raise RuntimeError(f"Transcript extraction too short ({len(paragraphs)} paragraphs) for {url}")
    return "\n\n".join(paragraphs)


def parse_vtt_to_timestamped_text(vtt_text: str) -> str:
    lines = vtt_text.splitlines()
    blocks = []
    cur_ts = None
    seen = set()
    buf = []

    def flush():
        nonlocal cur_ts, buf
        if cur_ts and buf:
            cleaned = re.sub(r"<[^>]+>", "", " ".join(buf))
            cleaned = html.unescape(re.sub(r"\s+", " ", cleaned)).strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                blocks.append((cur_ts, cleaned))
        buf = []

    for line in lines:
        s = line.strip()
        m = re.match(r"^(\d{2}:\d{2}:\d{2})\.\d+\s+-->\s+", s)
        if m:
            flush()
            cur_ts = m.group(1)
        elif s and not s.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            if not s.isdigit():
                buf.append(s)
    flush()

    # Merge tiny ASR fragments into readable ~30-second blocks
    merged = []
    cur_label = ""
    cur_words = []
    last_secs = -999
    for ts, text in blocks:
        hh, mm, ss = (int(x) for x in ts.split(":"))
        secs = hh * 3600 + mm * 60 + ss
        if not cur_label:
            cur_label = ts
            last_secs = secs
        if cur_words and secs - last_secs >= 25:
            merged.append(f"[{cur_label}] {' '.join(cur_words)}")
            cur_label = ts
            cur_words = [text]
            last_secs = secs
        else:
            cur_words.append(text)
    if cur_words:
        merged.append(f"[{cur_label}] {' '.join(cur_words)}")
    return "\n\n".join(merged)


def fetch_youtube_captions(url: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_tpl = str(pathlib.Path(tmpdir) / "ep.%(ext)s")
        subprocess.run(
            [
                "yt-dlp",
                "--skip-download",
                "--write-auto-subs",
                "--write-subs",
                "--sub-lang",
                "en,en-US,en-GB",
                "--sub-format",
                "vtt",
                "-o",
                out_tpl,
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        vtts = sorted(pathlib.Path(tmpdir).glob("*.vtt"))
        if not vtts:
            raise RuntimeError(f"No English VTT captions downloaded for {url}")
        return parse_vtt_to_timestamped_text(vtts[0].read_text(encoding="utf-8", errors="replace"))


def build_header(ep: dict, source_kind: str, orig_url: str) -> str:
    rep_lines = "\n".join(
        f"- {t['composer']}：{t['titleZh']}（{t['piece']}）" for t in ep.get("repertoire", [])
    )
    scene_lines = "\n".join(f"- {s}" for s in ep.get("scenes", []))
    return (
        f"标题：伯恩斯坦《青少年音乐会》第 {ep['id']} 集：{ep['titleZh']}（{ep['titleEn']}）\n"
        f"来源：{source_kind}（New York Philharmonic Young People's Concerts）\n"
        f"首播日期：{ep['date']}\n"
        f"原链接：{orig_url}\n"
        "说明：以下仅是这一主题的原始来源文本与已核验曲目表。"
        "不要把其它集数或未提及的人物、日期、年份、引语编造进幻灯片。\n\n"
        f"【核心提要】\n"
        f"核心概念：{ep['concepts']}\n"
        f"核心观点：{ep['thesis']}\n"
        f"讲解脉络：{ep['plain']}\n"
        f"现场示范：\n{scene_lines}\n\n"
        f"【本课已核验演奏曲目】\n{rep_lines}\n\n"
        "【原始讲稿 / 视频字幕原文】\n"
    )


def main():
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(EPISODES_JSON.read_text(encoding="utf-8"))
    manifest_path = SOURCES_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.is_file() else {}

    for ep in data["episodes"]:
        ep_id = ep["id"]
        key = str(ep_id)
        out_txt = SOURCES_DIR / f"ep-{ep_id:02d}.txt"
        existing = manifest.get(key)
        if existing and out_txt.is_file() and out_txt.stat().st_size > 800:
            continue

        script_url = ep.get("scriptUrl")
        yt_url = YOUTUBE_NON_SCRIPT.get(ep_id)

        if script_url:
            body = fetch_official_script(script_url)
            kind = "官方逐字讲稿（leonardbernstein.com）"
            orig_url = script_url
            source_type = "official_script"
            time.sleep(0.3)
        elif yt_url:
            body = fetch_youtube_captions(yt_url)
            kind = "YouTube 录像英文字幕 + 纽约爱乐档案"
            orig_url = yt_url
            source_type = "youtube_captions"
            time.sleep(0.5)
        else:
            raise RuntimeError(f"Episode {ep_id} has neither scriptUrl nor YouTube fallback!")

        full_text = build_header(ep, kind, orig_url) + body + "\n"
        out_txt.write_text(full_text, encoding="utf-8")
        sha = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        manifest[key] = {
            "id": ep_id,
            "file": str(out_txt.relative_to(ROOT)),
            "source_type": source_type,
            "url": orig_url,
            "youtube_url": yt_url,
            "sha256": sha,
            "chars": len(full_text),
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Prepared ep-{ep_id:02d}.txt ({source_type}, {len(full_text)} chars)")

    print(f"All {len(manifest)} sources ready in {SOURCES_DIR}")


if __name__ == "__main__":
    main()
