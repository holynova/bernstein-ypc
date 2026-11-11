#!/usr/bin/env python3
"""Orchestrate NotebookLM PPT slide generation, WebP extraction, and web publishing.

Follows hn-notebooklm-ppt invariants and yields gracefully whenever the sibling
project /Users/sym/code/podcast-atlas holds its cycle lock or cooldown window.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv/bin/python"
NLM_PY = pathlib.Path("/Users/sym/.local/share/uv/tools/notebooklm-mcp-cli/bin/python3")
NLM_ONCE = ROOT / "scripts/nlm_once.py"
OPTIMIZE_PY = ROOT / "scripts/optimize_slides.py"
BUILD_SLIDES_PY = ROOT / "scripts/build_slides.py"

EPISODES_JSON = ROOT / "src/data/episodes.json"
SLIDES_JSON = ROOT / "src/data/slides.json"
MANIFEST_JSON = ROOT / "work/sources/manifest.json"
STATE_FILE = ROOT / "state/progress.json"
CYCLE_LOCK = ROOT / "state/cycle.lock"
RUNNER_LOCK = ROOT / "state/runner.lock"
INCOMING_DIR = ROOT / "work/incoming"
PUBLIC_SLIDES_DIR = ROOT / "public/slides"
PORTFOLIO_REPO = pathlib.Path("/Users/sym/code/holynova.github.io")
PORTFOLIO_SUBDIR = PORTFOLIO_REPO / "bernstein-ypc"

SIBLING_ROOT = pathlib.Path("/Users/sym/code/podcast-atlas")
SIBLING_LOCK = SIBLING_ROOT / "state/cycle.lock"
SIBLING_DEFAULT_STATE = SIBLING_ROOT / "state/progress.json"
SIBLING_ACCOUNT_B_STATE = SIBLING_ROOT / "state/accounts/account-b.json"

TZ = dt.timezone(dt.timedelta(hours=8))

MAX_INFLIGHT_PER_ACCOUNT = 10
SUBMIT_INTERVAL_SECONDS = 60
INITIAL_WAIT_SECONDS = 1200
POLL_INTERVAL_SECONDS = 300
CLI_INTERVAL_SECONDS = 15
SINGLE_EP_RETRY_DELAY = 60
DAILY_FAIL_LIMIT = 3
SHORT_THROTTLE_SECONDS = 180
LONG_COOLDOWN_SECONDS = 18000

BUCKETS = {
    "bucket_1": {"title": "bernstein-ypc｜第01-27课", "profile": "account-b", "range": range(1, 28)},
    "bucket_2": {"title": "bernstein-ypc｜第28-53课", "profile": "default", "range": range(28, 54)},
}

_LAST_CLI_TS = 0.0
_PROXY_CACHE = None


def now_dt() -> dt.datetime:
    return dt.datetime.now(TZ)


def now_iso() -> str:
    return now_dt().isoformat(timespec="seconds")


def parse_iso(val: str | None) -> dt.datetime | None:
    if not val:
        return None
    try:
        parsed = dt.datetime.fromisoformat(val)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=TZ)
    except ValueError:
        return None


def log(msg: str):
    print(f"[{now_iso()}] {msg}", flush=True)


def build_base_env(profile: str | None = None) -> dict[str, str]:
    """Return environment with full Homebrew/local PATH, UTF-8, proxy, and profile."""
    global _PROXY_CACHE
    env = dict(os.environ)
    extra_bins = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/Users/sym/.local/bin",
        "/Users/sym/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override",
    ]
    current_path = env.get("PATH", "")
    env["PATH"] = ":".join(extra_bins + ([current_path] if current_path else []))
    env.setdefault("HOME", str(pathlib.Path.home()))
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    if profile:
        env["NLM_PROFILE"] = profile

    if _PROXY_CACHE is None:
        _PROXY_CACHE = {}
        if not any(env.get(k) for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")):
            try:
                out = subprocess.check_output(["/usr/sbin/scutil", "--proxy"], text=True, timeout=5)
                if re.search(r"HTTPSEnable\s*:\s*1", out):
                    host = re.search(r"HTTPSProxy\s*:\s*(\S+)", out)
                    port = re.search(r"HTTPSPort\s*:\s*(\d+)", out)
                    if host and port:
                        _PROXY_CACHE["https_proxy"] = f"http://{host.group(1)}:{port.group(1)}"
                        _PROXY_CACHE["HTTPS_PROXY"] = _PROXY_CACHE["https_proxy"]
                if re.search(r"HTTPEnable\s*:\s*1", out):
                    host = re.search(r"HTTPProxy\s*:\s*(\S+)", out)
                    port = re.search(r"HTTPPort\s*:\s*(\d+)", out)
                    if host and port:
                        _PROXY_CACHE["http_proxy"] = f"http://{host.group(1)}:{port.group(1)}"
                        _PROXY_CACHE["HTTP_PROXY"] = _PROXY_CACHE["http_proxy"]
            except Exception:
                pass
    env.update(_PROXY_CACHE)
    return env


def pace_cli():
    global _LAST_CLI_TS
    gap = time.monotonic() - _LAST_CLI_TS
    if _LAST_CLI_TS > 0 and gap < CLI_INTERVAL_SECONDS:
        time.sleep(CLI_INTERVAL_SECONDS - gap)
    _LAST_CLI_TS = time.monotonic()


def run_nlm_json(args: list[str], profile: str, timeout: int = 120):
    """Execute nlm via non-retrying nlm_once.py wrapper and parse JSON."""
    pace_cli()
    cmd = [str(NLM_PY), str(NLM_ONCE), *args]
    if "--profile" not in cmd:
        cmd.extend(["--profile", profile])
    res = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=build_base_env(profile),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "").strip()
        raise RuntimeError(f"nlm {' '.join(args[:2])} failed ({res.returncode}): {err}")
    raw = (res.stdout or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        idx = min([i for i in (raw.find("{"), raw.find("[")) if i >= 0], default=-1)
        if idx >= 0:
            return json.loads(raw[idx:])
        raise RuntimeError(f"Non-JSON nlm output: {raw[:240]}")


def sibling_lock_held() -> bool:
    if not SIBLING_LOCK.exists():
        return False
    with SIBLING_LOCK.open("r") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True


def sibling_account_cooldown(profile: str) -> dt.datetime | None:
    path = SIBLING_DEFAULT_STATE if profile == "default" else SIBLING_ACCOUNT_B_STATE
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return parse_iso(data.get("generation_cooldown_until"))
    except Exception:
        return None


def bucket_for_ep(ep_id: int) -> tuple[str, dict]:
    for key, spec in BUCKETS.items():
        if ep_id in spec["range"]:
            return key, spec
    raise ValueError(f"Episode {ep_id} not mapped to any notebook bucket")


def with_state_lock(fn):
    RUNNER_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with RUNNER_LOCK.open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
            result = fn(state)
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            tmp.replace(STATE_FILE)
            return result
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def init_state():
    ep_data = json.loads(EPISODES_JSON.read_text())["episodes"]
    manifest = json.loads(MANIFEST_JSON.read_text())
    slides = json.loads(SLIDES_JSON.read_text()) if SLIDES_JSON.exists() else {}
    episodes_by_id = {ep["id"]: ep for ep in ep_data}

    def _sync(state: dict):
        state.setdefault("schema_version", 1)
        nbs = state.setdefault("notebooks", {})
        for bkey, spec in BUCKETS.items():
            entry = nbs.setdefault(bkey, {})
            entry["title"] = spec["title"]
            entry["profile"] = spec["profile"]
            entry.setdefault("notebook_id", None)
            entry.setdefault("last_polled_at", None)

        accts = state.setdefault("accounts", {})
        for prof in ("default", "account-b"):
            a = accts.setdefault(prof, {})
            a.setdefault("cooldown_until", None)
            a.setdefault("last_submit_at", None)
            a.setdefault("last_error", None)

        eps_state = state.setdefault("episodes", {})
        today = now_dt().strftime("%Y-%m-%d")
        for ep_id, ep in episodes_by_id.items():
            bkey, spec = bucket_for_ep(ep_id)
            key = str(ep_id)
            rec = eps_state.setdefault(key, {})
            m = manifest[key]
            rec["id"] = ep_id
            rec["item_id"] = f"ep-{ep_id:02d}"
            rec["bucket"] = bkey
            rec["profile"] = spec["profile"]
            rec["source_title"] = f"ep-{ep_id:02d}｜{ep['titleZh']}"
            rec["source_file"] = m["file"]
            rec["source_sha256"] = m["sha256"]
            rec.setdefault("source_id", None)
            rec.setdefault("slide_status", "pending")
            rec.setdefault("artifact_id", None)
            rec.setdefault("failed_artifact_ids", [])
            rec.setdefault("submitted_at", None)
            rec.setdefault("next_attempt_at", None)
            rec.setdefault("failed_date", None)
            rec.setdefault("failed_today", 0)
            if rec.get("failed_date") and rec["failed_date"] != today:
                rec["failed_date"] = today
                rec["failed_today"] = 0
            rec.setdefault("attempts", 0)
            rec.setdefault("history", [])
            rec.setdefault("pdf_path", None)
            rec.setdefault("pages", 0)
            rec.setdefault("published", False)

            if key in slides and slides[key].get("pages", 0) > 0:
                rec["slide_status"] = "complete"
                rec["pages"] = slides[key]["pages"]
                pdf_rel = f"public/slides/ep-{ep_id:02d}.pdf"
                if (ROOT / pdf_rel).exists():
                    rec["pdf_path"] = pdf_rel

        return state

    return with_state_lock(_sync), episodes_by_id


def account_cooldown_until(state: dict, profile: str) -> dt.datetime | None:
    local = parse_iso(state["accounts"][profile].get("cooldown_until"))
    sib = sibling_account_cooldown(profile)
    cands = [x for x in (local, sib) if x is not None]
    return max(cands) if cands else None


def is_account_cooling(state: dict, profile: str) -> bool:
    until = account_cooldown_until(state, profile)
    return bool(until and until > now_dt())


def ensure_notebook(bkey: str) -> str:
    state = json.loads(STATE_FILE.read_text())
    nb_meta = state["notebooks"][bkey]
    if nb_meta.get("notebook_id"):
        return nb_meta["notebook_id"]

    profile = nb_meta["profile"]
    title = nb_meta["title"]
    listed = run_nlm_json(["notebook", "list", "--json"], profile)
    items = listed if isinstance(listed, list) else listed.get("notebooks", [])
    found = next((n for n in items if n.get("title") == title), None)
    if not found:
        log(f"Creating notebook '{title}' on profile '{profile}'")
        found = run_nlm_json(["notebook", "create", title, "--json"], profile)
    nb_id = found.get("notebook_id") or found.get("id")
    if not nb_id:
        raise RuntimeError(f"Failed to resolve notebook ID for {title}")

    def _save(s):
        s["notebooks"][bkey]["notebook_id"] = nb_id

    with_state_lock(_save)
    return nb_id


def list_sources_cached(nb_id: str, profile: str, cache: dict) -> list[dict]:
    if nb_id not in cache:
        raw = run_nlm_json(["source", "list", nb_id, "--json"], profile)
        cache[nb_id] = raw if isinstance(raw, list) else raw.get("sources", [])
    return cache[nb_id]


def ensure_source(ep_id: int, source_cache: dict) -> tuple[str, str]:
    state = json.loads(STATE_FILE.read_text())
    rec = state["episodes"][str(ep_id)]
    bkey = rec["bucket"]
    profile = rec["profile"]
    nb_id = ensure_notebook(bkey)
    if rec.get("source_id"):
        return nb_id, rec["source_id"]

    prefix = f"ep-{ep_id:02d}｜"
    items = list_sources_cached(nb_id, profile, source_cache)
    found = next((s for s in items if str(s.get("title", "")).startswith(prefix)), None)
    if not found:
        src_file = ROOT / rec["source_file"]
        log(f"Uploading {src_file.name} -> {bkey} ({profile})")
        found = run_nlm_json(
            ["source", "add", nb_id, "--file", str(src_file), "--title", rec["source_title"], "--wait", "--json"],
            profile,
            timeout=660,
        )
        source_cache.pop(nb_id, None)

    src_id = found.get("source_id") or found.get("id")
    if not src_id:
        raise RuntimeError(f"Failed to resolve source ID for ep-{ep_id:02d}")

    def _save(s):
        s["episodes"][str(ep_id)]["source_id"] = src_id

    with_state_lock(_save)
    return nb_id, src_id


def build_focus_prompt(ep: dict) -> str:
    ep_id = ep["id"]
    return (
        f"标识 ep-{ep_id:02d}。"
        f"围绕第 {ep_id} 集《{ep['titleZh']}》（{ep['titleEn']}）制作简体中文详细学习幻灯片，严格控制在恰好 15 页（15 张幻灯片）："
        "第 1 页为手绘海报风封面；第 2-4 页交代本课时代背景与核心发问；"
        "第 5-11 页逐层拆解核心乐理概念与伯恩斯坦现场对照实验；"
        "第 12-13 页提炼关键音乐片段的听辨线索；"
        "第 14 页按来路梳理本课演奏曲目表；第 15 页给出全课收获总结。"
        "视觉严格采用《丁丁历险记》清线漫画（Ligne Claire）风格：黑色清晰轮廓、鲜明平涂色块、"
        "还原纽约卡内基音乐厅或林肯中心舞台、钢琴与乐队群像，配简练精准的中文解说短句。"
        "严格只使用所选来源中的事实、人名、日期、乐曲与引语，绝不虚构或混入其它集数内容；"
        "不要把文件名或标识编号写进幻灯片标题。"
    )


def fetch_artifacts(nb_id: str, profile: str) -> list[dict]:
    raw = run_nlm_json(["studio", "status", nb_id, "--full", "--json", "--limit", "100"], profile)
    if isinstance(raw, list):
        return raw
    return raw.get("artifacts", raw.get("data", []))


def artifact_matches_ep(artifact: dict, ep_id: int, source_id: str | None) -> bool:
    item_id = f"ep-{ep_id:02d}"
    blob = json.dumps(artifact, ensure_ascii=False)
    if f"标识 {item_id}" in blob or f"{item_id}｜" in blob or item_id in blob:
        return True
    if source_id and source_id in (artifact.get("source_ids") or []):
        return True
    return False


def download_and_build(ep_id: int, nb_id: str, artifact_id: str, profile: str) -> int:
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_SLIDES_DIR.mkdir(parents=True, exist_ok=True)
    part_pdf = INCOMING_DIR / f"ep-{ep_id:02d}.part.pdf"
    pub_pdf = PUBLIC_SLIDES_DIR / f"ep-{ep_id:02d}.pdf"
    part_pdf.unlink(missing_ok=True)

    pace_cli()
    res = subprocess.run(
        [
            "/Users/sym/.local/bin/nlm",
            "download",
            "slide-deck",
            nb_id,
            "--id",
            artifact_id,
            "--output",
            str(part_pdf),
            "--no-progress",
        ],
        cwd=str(ROOT),
        env=build_base_env(profile),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout or "download failed").strip())
    if not part_pdf.exists() or part_pdf.read_bytes()[:5] != b"%PDF-":
        raise RuntimeError(f"Downloaded file for ep-{ep_id:02d} is not a PDF")

    pages = len(PdfReader(part_pdf).pages)
    if pages < 1:
        raise RuntimeError(f"Downloaded PDF for ep-{ep_id:02d} has 0 pages")
    if pages != 15:
        log(f"Notice: ep-{ep_id:02d} generated {pages} pages (requested 15)")

    part_pdf.replace(pub_pdf)
    subprocess.run([str(VENV_PY), str(OPTIMIZE_PY), str(pub_pdf)], cwd=str(ROOT), env=build_base_env(), check=True, timeout=180)
    subprocess.run([str(VENV_PY), str(BUILD_SLIDES_PY)], cwd=str(ROOT), env=build_base_env(), check=True, timeout=300)

    slides = json.loads(SLIDES_JSON.read_text()) if SLIDES_JSON.exists() else {}
    rendered_pages = slides.get(str(ep_id), {}).get("pages", pages)

    def _mark_done(s):
        r = s["episodes"][str(ep_id)]
        r["slide_status"] = "complete"
        r["artifact_id"] = artifact_id
        r["pdf_path"] = f"public/slides/ep-{ep_id:02d}.pdf"
        r["pages"] = rendered_pages
        r["published"] = False
        r["history"].append({"at": now_iso(), "event": "complete", "artifact_id": artifact_id, "pages": rendered_pages})

    with_state_lock(_mark_done)
    log(f"Completed ep-{ep_id:02d} -> {rendered_pages} WebP slides + PDF ready")
    return rendered_pages


def process_local_unbuilt_pdfs() -> int:
    """Convert any PDFs in public/slides/ not yet reflected in src/data/slides.json."""
    if not PUBLIC_SLIDES_DIR.exists():
        return 0
    slides = json.loads(SLIDES_JSON.read_text()) if SLIDES_JSON.exists() else {}
    unbuilt = []
    for pdf in sorted(PUBLIC_SLIDES_DIR.glob("ep-*.pdf")):
        m = re.match(r"^ep-(\d+)$", pdf.stem)
        if not m:
            continue
        ep_id = int(m.group(1))
        if str(ep_id) not in slides:
            unbuilt.append((ep_id, pdf))
    if not unbuilt:
        return 0
    for _, pdf in unbuilt:
        subprocess.run([str(VENV_PY), str(OPTIMIZE_PY), str(pdf)], cwd=str(ROOT), env=build_base_env(), check=True, timeout=180)
    subprocess.run([str(VENV_PY), str(BUILD_SLIDES_PY)], cwd=str(ROOT), env=build_base_env(), check=True, timeout=300)
    updated_slides = json.loads(SLIDES_JSON.read_text())

    def _sync_done(s):
        for ep_id, _ in unbuilt:
            key = str(ep_id)
            if key in updated_slides:
                r = s["episodes"][key]
                r["slide_status"] = "complete"
                r["pdf_path"] = f"public/slides/ep-{ep_id:02d}.pdf"
                r["pages"] = updated_slides[key]["pages"]

    with_state_lock(_sync_done)
    return len(unbuilt)


def poll_ready_notebooks(reconcile_now: bool = False) -> tuple[int, bool]:
    """Poll each notebook at most once when ready; download finished decks. Returns (built_count, remote_blocked)."""
    if sibling_lock_held():
        return 0, True

    state = json.loads(STATE_FILE.read_text())
    now = now_dt()
    built = 0

    for bkey, nb_meta in state["notebooks"].items():
        nb_id = nb_meta.get("notebook_id")
        if not nb_id:
            continue
        profile = nb_meta["profile"]
        inflight = [
            rec
            for rec in state["episodes"].values()
            if rec["bucket"] == bkey and rec["slide_status"] in {"submitting", "queued", "generating", "running", "in_progress"}
        ]
        if not inflight:
            continue

        last_poll = parse_iso(nb_meta.get("last_polled_at"))
        if not reconcile_now and last_poll and (now - last_poll).total_seconds() < POLL_INTERVAL_SECONDS:
            continue

        ready_to_check = []
        for rec in inflight:
            sub_at = parse_iso(rec.get("submitted_at"))
            if reconcile_now or sub_at is None or (now - sub_at).total_seconds() >= INITIAL_WAIT_SECONDS:
                ready_to_check.append(rec)
        if not ready_to_check:
            continue

        if sibling_lock_held():
            return built, True

        log(f"Polling studio status for {bkey} ({profile}, {len(ready_to_check)} due)")
        artifacts = fetch_artifacts(nb_id, profile)

        def _touch_poll(s):
            s["notebooks"][bkey]["last_polled_at"] = now_iso()

        with_state_lock(_touch_poll)

        for rec in ready_to_check:
            ep_id = rec["id"]
            failed_ids = set(rec.get("failed_artifact_ids", []))
            matches = [
                a
                for a in artifacts
                if artifact_matches_ep(a, ep_id, rec.get("source_id"))
                and (a.get("artifact_id") or a.get("id")) not in failed_ids
            ]

            tracked_id = rec.get("artifact_id")
            if tracked_id and not any((a.get("artifact_id") or a.get("id")) == tracked_id for a in matches):
                exact = next((a for a in artifacts if (a.get("artifact_id") or a.get("id")) == tracked_id), None)
                if exact and tracked_id not in failed_ids:
                    matches.append(exact)

            completed = [a for a in matches if str(a.get("status", "")).lower() in {"completed", "complete", "ready", "3"}]
            if completed:
                art = completed[-1]
                art_id = art.get("artifact_id") or art.get("id")
                try:
                    download_and_build(ep_id, nb_id, art_id, profile)
                    built += 1
                except Exception as exc:
                    log(f"Download/build failed for ep-{ep_id:02d}: {exc}")
                continue

            failed = [a for a in matches if str(a.get("status", "")).lower() in {"failed", "error", "4"}]
            active = [a for a in matches if str(a.get("status", "")).lower() not in {"failed", "error", "4"}]
            if active:
                art_id = active[-1].get("artifact_id") or active[-1].get("id")

                def _keep_waiting(s):
                    r = s["episodes"][str(ep_id)]
                    r["artifact_id"] = art_id
                    r["slide_status"] = "queued"

                with_state_lock(_keep_waiting)
                continue

            if failed or rec["slide_status"] == "submitting":
                def _mark_failed(s):
                    r = s["episodes"][str(ep_id)]
                    today = now_dt().strftime("%Y-%m-%d")
                    if r.get("failed_date") != today:
                        r["failed_date"] = today
                        r["failed_today"] = 0
                    for fa in failed:
                        fid = fa.get("artifact_id") or fa.get("id")
                        if fid and fid not in r["failed_artifact_ids"]:
                            r["failed_artifact_ids"].append(fid)
                    r["artifact_id"] = None
                    r["slide_status"] = "failed"
                    r["failed_today"] += 1
                    r["next_attempt_at"] = (now_dt() + dt.timedelta(seconds=SINGLE_EP_RETRY_DELAY)).isoformat(timespec="seconds")
                    r["history"].append({"at": now_iso(), "event": "failed", "reason": "remote_failed" if failed else "missing_submitting_artifact"})

                with_state_lock(_mark_failed)
                log(f"Marked ep-{ep_id:02d} failed for safe retry (+60s)")

    return built, False


def submit_eligible(episodes_by_id: dict[int, dict], max_new: int, remaining_new: int, source_cache: dict, dry_run: bool = False) -> tuple[int, bool]:
    """Submit up to remaining_new slides respecting concurrency, pacing, and cooldowns."""
    if remaining_new <= 0 or sibling_lock_held():
        return 0, sibling_lock_held()

    state = json.loads(STATE_FILE.read_text())
    now = now_dt()
    inflight_by_acct = {"default": 0, "account-b": 0}
    for rec in state["episodes"].values():
        if rec["slide_status"] in {"submitting", "queued", "generating", "running", "in_progress"}:
            inflight_by_acct[rec["profile"]] = inflight_by_acct.get(rec["profile"], 0) + 1

    candidates = []
    for rec in state["episodes"].values():
        if rec["slide_status"] not in {"pending", "failed", "retry_pending"}:
            continue
        if rec.get("failed_today", 0) >= DAILY_FAIL_LIMIT:
            continue
        nxt = parse_iso(rec.get("next_attempt_at"))
        if nxt and nxt > now:
            continue
        candidates.append(rec)

    # Starvation-prevention: lowest daily fail count first, then episode order.
    candidates.sort(key=lambda r: (r.get("failed_today", 0), r["id"]))

    submitted = 0
    for rec in candidates:
        if submitted >= remaining_new:
            break
        if sibling_lock_held():
            return submitted, True

        profile = rec["profile"]
        state = json.loads(STATE_FILE.read_text())
        if is_account_cooling(state, profile):
            continue
        if inflight_by_acct.get(profile, 0) >= MAX_INFLIGHT_PER_ACCOUNT:
            continue

        last_sub = parse_iso(state["accounts"][profile].get("last_submit_at"))
        if not dry_run and last_sub:
            wait_sec = SUBMIT_INTERVAL_SECONDS - (now_dt() - last_sub).total_seconds()
            if wait_sec > 0:
                time.sleep(wait_sec)
                if sibling_lock_held():
                    return submitted, True

        ep_id = rec["id"]
        ep = episodes_by_id[ep_id]
        if dry_run:
            log(f"[dry-run] Would submit ep-{ep_id:02d} ({ep['titleZh']}) on {profile} / {rec['bucket']}")
            inflight_by_acct[profile] += 1
            submitted += 1
            continue

        nb_id, src_id = ensure_source(ep_id, source_cache)
        focus = build_focus_prompt(ep)

        def _pre_submit(s):
            r = s["episodes"][str(ep_id)]
            r["slide_status"] = "submitting"
            r["submitted_at"] = now_iso()
            r["attempts"] += 1
            s["accounts"][profile]["last_submit_at"] = r["submitted_at"]

        with_state_lock(_pre_submit)
        log(f"Submitting slides for ep-{ep_id:02d} ({ep['titleZh']}) on {profile}")

        try:
            resp = run_nlm_json(
                [
                    "slides",
                    "create",
                    nb_id,
                    "--source-ids",
                    src_id,
                    "--format",
                    "detailed_deck",
                    "--length",
                    "default",
                    "--language",
                    "zh-CN",
                    "--focus",
                    focus,
                    "--confirm",
                    "--json",
                ],
                profile,
                timeout=120,
            )
        except Exception as exc:
            err = str(exc)
            is_429 = any(tok in err.lower() for tok in ("429", "rate limit", "resource_exhausted", "too many requests", "exhausted"))
            short_throttle = any(tok in err.lower() for tok in ("wait 1-2 minutes", "wait a few minutes"))
            if is_429 or short_throttle:
                delay = SHORT_THROTTLE_SECONDS if short_throttle else LONG_COOLDOWN_SECONDS
                until = (now_dt() + dt.timedelta(seconds=delay)).isoformat(timespec="seconds")

                def _cool(s):
                    s["accounts"][profile]["cooldown_until"] = until
                    s["accounts"][profile]["last_error"] = err[:400]
                    r = s["episodes"][str(ep_id)]
                    r["slide_status"] = "retry_pending"
                    r["next_attempt_at"] = until
                    r["history"].append({"at": now_iso(), "event": "rate_limited", "until": until, "error": err[:240]})

                with_state_lock(_cool)
                log(f"Account {profile} rate-limited until {until}; preserving inflight tasks")
            else:
                def _fail_sub(s):
                    r = s["episodes"][str(ep_id)]
                    today = now_dt().strftime("%Y-%m-%d")
                    if r.get("failed_date") != today:
                        r["failed_date"] = today
                        r["failed_today"] = 0
                    r["slide_status"] = "failed"
                    r["failed_today"] += 1
                    r["next_attempt_at"] = (now_dt() + dt.timedelta(seconds=SINGLE_EP_RETRY_DELAY)).isoformat(timespec="seconds")
                    r["history"].append({"at": now_iso(), "event": "submit_error", "error": err[:240]})

                with_state_lock(_fail_sub)
                log(f"Submit failed for ep-{ep_id:02d}: {err[:200]}")
            continue

        art_id = resp.get("artifact_id") or resp.get("id")

        def _post_submit(s):
            r = s["episodes"][str(ep_id)]
            r["artifact_id"] = art_id
            r["slide_status"] = "queued"
            r["history"].append({"at": now_iso(), "event": "submitted", "artifact_id": art_id})

        with_state_lock(_post_submit)
        inflight_by_acct[profile] += 1
        submitted += 1
        log(f"Queued ep-{ep_id:02d} -> artifact {art_id}")

    return submitted, False


def publish_site():
    """Verify, build, commit, push, and deploy bernstein-ypc if new decks exist."""
    env = build_base_env()
    subprocess.run(["npm", "run", "build"], cwd=str(ROOT), env=env, check=True, timeout=180)
    subprocess.run(["npm", "test"], cwd=str(ROOT), env=env, check=True, timeout=120)

    slides = json.loads(SLIDES_JSON.read_text()) if SLIDES_JSON.exists() else {}
    count = len(slides)

    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--", "src/data/slides.json", "public/static", "public/slides"],
        cwd=str(ROOT),
        env=env,
        text=True,
    ).strip()
    if status:
        subprocess.run(["git", "add", "--", "src/data/slides.json", "public/static", "public/slides"], cwd=str(ROOT), env=env, check=True)
        diff_cached = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(ROOT), env=env)
        if diff_cached.returncode != 0:
            subprocess.run(["git", "commit", "-m", f"Publish WebP PPT slides ({count}/53 episodes)"], cwd=str(ROOT), env=env, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=str(ROOT), env=env, check=True, timeout=120)

    if not PORTFOLIO_REPO.exists():
        log(f"Portfolio repo missing at {PORTFOLIO_REPO}; skipping deploy")
        return

    PORTFOLIO_SUBDIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsync", "-a", "--delete", f"{ROOT / 'dist'}/", f"{PORTFOLIO_SUBDIR}/"], env=env, check=True, timeout=120)
    p_status = subprocess.check_output(
        ["git", "status", "--porcelain", "--", "bernstein-ypc"],
        cwd=str(PORTFOLIO_REPO),
        env=env,
        text=True,
    ).strip()
    if p_status:
        subprocess.run(["git", "add", "--", "bernstein-ypc"], cwd=str(PORTFOLIO_REPO), env=env, check=True)
        subprocess.run(["git", "commit", "-m", f"Update bernstein-ypc slides ({count}/53 decks)"], cwd=str(PORTFOLIO_REPO), env=env, check=True)
        subprocess.run(["git", "push", "origin", "master"], cwd=str(PORTFOLIO_REPO), env=env, check=True, timeout=120)
        subprocess.run(["npx", "--yes", "wrangler@4.128.0", "deploy", "--config", "wrangler.jsonc"], cwd=str(PORTFOLIO_REPO), env=env, check=True, timeout=180)
        log(f"Deployed live site with {count}/53 WebP slide decks")

        def _mark_pub(s):
            for k in slides:
                if k in s["episodes"] and s["episodes"][k]["slide_status"] == "complete":
                    s["episodes"][k]["published"] = True

        with_state_lock(_mark_pub)


def all_complete(state: dict) -> bool:
    return all(rec["slide_status"] == "complete" for rec in state["episodes"].values())


def main():
    parser = argparse.ArgumentParser(description="Run Bernstein YPC NotebookLM PPT pipeline cycle.")
    parser.add_argument("--wait-minutes", type=int, default=150, help="Cycle budget in minutes (0 = single pass).")
    parser.add_argument("--limit", type=int, default=20, help="Max new slide submissions in this cycle.")
    parser.add_argument("--status-only", action="store_true", help="Only reconcile/download/build; do not submit new.")
    parser.add_argument("--reconcile-now", action="store_true", help="Ignore 20m wait guard for polling.")
    parser.add_argument("--publish", action="store_true", help="Rebuild, push, and deploy when new slides complete.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned submissions without calling nlm.")
    args = parser.parse_args()

    CYCLE_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with CYCLE_LOCK.open("w") as flock:
        try:
            fcntl.flock(flock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("Another bernstein-ypc ppt_cycle instance is running; exiting cleanly.")
            return 0

        state, episodes_by_id = init_state()
        built_local = process_local_unbuilt_pdfs()
        if built_local:
            log(f"Built {built_local} unbuilt local PDFs into WebP decks.")
            state = json.loads(STATE_FILE.read_text())

        done_count = sum(1 for r in state["episodes"].values() if r["slide_status"] == "complete")
        log(f"Cycle start: {done_count}/53 complete, sibling_lock={sibling_lock_held()}")

        if all_complete(state):
            log("All 53/53 slide decks are complete!")
            if args.publish and not args.dry_run:
                publish_site()
                subprocess.run(
                    ["/bin/launchctl", "disable", f"gui/{os.getuid()}/com.bernstein-ypc.ppt-cycle"],
                    check=False,
                    capture_output=True,
                )
            return 0

        if sibling_lock_held():
            log("Deferring remote nlm calls: podcast-atlas cycle.lock is active.")
            if args.publish and built_local and not args.dry_run:
                publish_site()
            return 0

        deadline = time.monotonic() + max(0, args.wait_minutes) * 60
        source_cache = {}
        total_built = built_local
        total_submitted = 0

        if not args.dry_run:
            built, blocked = poll_ready_notebooks(reconcile_now=args.reconcile_now)
            total_built += built
        else:
            blocked = False

        if not args.status_only and not blocked:
            sub, blocked = submit_eligible(
                episodes_by_id, args.limit, args.limit - total_submitted, source_cache, dry_run=args.dry_run
            )
            total_submitted += sub

        while not args.dry_run and not args.status_only and time.monotonic() < deadline:
            state = json.loads(STATE_FILE.read_text())
            inflight = [
                r for r in state["episodes"].values()
                if r["slide_status"] in {"submitting", "queued", "generating", "running", "in_progress"}
            ]
            if not inflight:
                break

            now = now_dt()
            next_wake = now + dt.timedelta(seconds=POLL_INTERVAL_SECONDS)
            for rec in inflight:
                sub_at = parse_iso(rec.get("submitted_at"))
                if sub_at:
                    due = sub_at + dt.timedelta(seconds=INITIAL_WAIT_SECONDS)
                    if due > now and due < next_wake:
                        next_wake = due
            sleep_sec = max(30.0, min((next_wake - now).total_seconds(), deadline - time.monotonic()))
            if sleep_sec <= 5:
                break
            log(f"Waiting {int(sleep_sec)}s ({len(inflight)} inflight; deadline in {int(deadline - time.monotonic())}s)")
            time.sleep(sleep_sec)

            if sibling_lock_held():
                log("Sibling podcast-atlas became active during wait; yielding cleanly.")
                break

            built, blocked = poll_ready_notebooks()
            total_built += built
            if not blocked and total_submitted < args.limit:
                sub, _ = submit_eligible(episodes_by_id, args.limit, args.limit - total_submitted, source_cache)
                total_submitted += sub

        state = json.loads(STATE_FILE.read_text())
        done_count = sum(1 for r in state["episodes"].values() if r["slide_status"] == "complete")
        pending_pub = any(r["slide_status"] == "complete" and not r.get("published") for r in state["episodes"].values())
        log(f"Cycle end: {done_count}/53 complete | submitted={total_submitted} | newly_built={total_built}")

        if args.publish and not args.dry_run and (total_built > 0 or pending_pub):
            publish_site()

        final_state = json.loads(STATE_FILE.read_text())
        if all_complete(final_state):
            log("All 53/53 slide decks completed and synced; disabling recurring LaunchAgent.")
            subprocess.run(
                ["/bin/launchctl", "disable", f"gui/{os.getuid()}/com.bernstein-ypc.ppt-cycle"],
                check=False,
                capture_output=True,
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
