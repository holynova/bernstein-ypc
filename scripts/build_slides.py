#!/usr/bin/env python3
"""Render cached, high-clarity WebP slide decks without secondary resampling.

Extracts raw embedded image streams directly for unpatched pages and falls
back to 2x Poppler supersampling only for pages with vector overlays.
Writes static WebPs into public/static/<16hex>/ and updates src/data/slides.json.
"""
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageChops
from pypdf import PdfReader

POPPLER_BIN = "/Users/sym/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm"
CWEBP_BIN = "/opt/homebrew/bin/cwebp"
RECIPE_TAG = b"slides-v2:uncomp-q90-sharp"
BASE_PATH = "/bernstein-ypc"


def find_tool(preferred: str, name: str):
    if pathlib.Path(preferred).is_file():
        return preferred
    return shutil.which(name)


def flatten_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return image.convert("RGB")


def macro_hot_tiles(img_a: Image.Image, img_b: Image.Image) -> int:
    if img_a.size != img_b.size:
        return 9999
    thumb_a = img_a.resize((64, 36), Image.Resampling.BILINEAR)
    thumb_b = img_b.resize((64, 36), Image.Resampling.BILINEAR)
    diff = (
        ImageChops.difference(thumb_a, thumb_b).get_flattened_data()
        if hasattr(thumb_a, "get_flattened_data")
        else ImageChops.difference(thumb_a, thumb_b).getdata()
    )
    return sum(1 for r, g, b in diff if (r + g + b) / 3 > 12)


def has_vector_overlay(pub_page) -> bool:
    if pub_page.extract_text().strip():
        return True
    if len(pub_page.images) != 1:
        return True
    contents = pub_page.get_contents()
    if contents is None:
        return False
    if hasattr(contents, "get_data"):
        return len(contents.get_data()) > 200
    return sum(len(s.get_object().get_data()) for s in contents) > 200


def render_overlay_page(pdf: pathlib.Path, page_num: int, pdftoppm: str, tmpdir: str, target_size):
    prefix = str(pathlib.Path(tmpdir) / f"ov-{page_num}")
    subprocess.run(
        [pdftoppm, "-f", str(page_num), "-l", str(page_num), "-singlefile", "-scale-to", "2752", str(pdf), prefix],
        check=True,
    )
    ppm_path = next(iter(sorted(pathlib.Path(tmpdir).glob(f"ov-{page_num}.p?m"))))
    with Image.open(ppm_path) as rendered:
        img = flatten_rgb(rendered)
        if img.size != target_size:
            img = img.resize(target_size, Image.Resampling.LANCZOS)
        return img


def encode_webp(image: Image.Image, out_path: pathlib.Path, tmp_ppm: pathlib.Path, cwebp: str | None):
    if cwebp:
        image.save(tmp_ppm, "PPM")
        subprocess.run([cwebp, "-quiet", "-q", "90", "-m", "4", "-sharp_yuv", str(tmp_ppm), "-o", str(out_path)], check=True)
        tmp_ppm.unlink(missing_ok=True)
    else:
        image.save(out_path, "WEBP", quality=90, method=4)


def copy_cached_deck(src_dir: pathlib.Path, dst_dir: pathlib.Path, pages: int):
    dst_dir.mkdir(parents=True, exist_ok=True)
    for page in range(1, pages + 1):
        name = f"{page}.webp"
        dst = dst_dir / name
        src = src_dir / name
        if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, dst)


def build_deck(args):
    pdf, uncomp_dir, cache, public_static, pdftoppm, cwebp, cached_entry = args
    stat = pdf.stat()
    ep_num = int(re.search(r"(\d+)", pdf.stem).group(1))
    if (
        cached_entry
        and cached_entry.get("recipe") == RECIPE_TAG.decode()
        and cached_entry.get("size") == stat.st_size
        and cached_entry.get("mtime_ns") == stat.st_mtime_ns
    ):
        key = cached_entry["key"]
        deck_cache = cache / key
        meta_path = deck_cache / "meta.json"
        if meta_path.is_file():
            pages = json.loads(meta_path.read_text()).get("pages", 0)
            if pages > 0 and all((deck_cache / f"{p}.webp").is_file() for p in range(1, pages + 1)):
                copy_cached_deck(deck_cache, public_static / key, pages)
                return str(ep_num), {
                    "prefix": f"{BASE_PATH}/static/{key}/",
                    "pdfUrl": f"{BASE_PATH}/slides/{pdf.name}",
                    "pages": pages,
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "key": key,
                }

    raw = pdf.read_bytes()
    key = hashlib.sha256(raw + RECIPE_TAG).hexdigest()[:16]
    deck_cache = cache / key
    meta_path = deck_cache / "meta.json"
    if not meta_path.is_file():
        pub_reader = PdfReader(io.BytesIO(raw))
        uncomp_path = uncomp_dir / f"{pdf.stem}-uncompressed.pdf"
        uncomp_reader = PdfReader(uncomp_path) if uncomp_path.is_file() else None
        if uncomp_reader and len(uncomp_reader.pages) != len(pub_reader.pages):
            uncomp_reader = None

        tmp_cache = cache / f"{key}.tmp-{os.getpid()}-{pdf.stem}"
        if tmp_cache.exists():
            shutil.rmtree(tmp_cache)
        tmp_cache.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_ppm = pathlib.Path(tmpdir) / "frame.ppm"
                for idx, pub_page in enumerate(pub_reader.pages, 1):
                    target_w = round(float(pub_page.mediabox.width))
                    target_h = round(float(pub_page.mediabox.height))
                    if has_vector_overlay(pub_page):
                        if not pdftoppm:
                            raise RuntimeError("Overlay slide pages require Poppler pdftoppm.")
                        frame = render_overlay_page(pdf, idx, pdftoppm, tmpdir, (target_w, target_h))
                    else:
                        with Image.open(io.BytesIO(pub_page.images[0].data)) as pub_im:
                            pub_rgb = flatten_rgb(pub_im)
                        frame = pub_rgb
                        if uncomp_reader and len(uncomp_reader.pages[idx - 1].images) == 1:
                            with Image.open(io.BytesIO(uncomp_reader.pages[idx - 1].images[0].data)) as u_im:
                                u_rgb = flatten_rgb(u_im)
                            if macro_hot_tiles(u_rgb, pub_rgb) <= 5:
                                frame = u_rgb
                    encode_webp(frame, tmp_cache / f"{idx}.webp", tmp_ppm, cwebp)
                (tmp_cache / "meta.json").write_text(json.dumps({"pages": len(pub_reader.pages)}))
            if deck_cache.exists():
                shutil.rmtree(tmp_cache)
            else:
                tmp_cache.replace(deck_cache)
        finally:
            if tmp_cache.exists():
                shutil.rmtree(tmp_cache, ignore_errors=True)

    pages = json.loads(meta_path.read_text())["pages"]
    copy_cached_deck(deck_cache, public_static / key, pages)
    return str(ep_num), {
        "prefix": f"{BASE_PATH}/static/{key}/",
        "pdfUrl": f"{BASE_PATH}/slides/{pdf.name}",
        "pages": pages,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "key": key,
    }


def main(root_arg: str | None = None):
    root = pathlib.Path(root_arg) if root_arg else pathlib.Path(__file__).resolve().parents[1]
    slides_dir = root / "public/slides"
    public_static = root / "public/static"
    out_json = root / "src/data/slides.json"
    cache = root / "work/site-slides"
    uncomp_dir = root / "work/slides"
    cache.mkdir(parents=True, exist_ok=True)
    public_static.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(slides_dir.glob("ep-*.pdf"))
    if not pdfs:
        out_json.write_text("{}\n", encoding="utf-8")
        print("Built 0 slide decks.")
        return

    pdftoppm = find_tool(POPPLER_BIN, "pdftoppm")
    cwebp = find_tool(CWEBP_BIN, "cwebp")
    index_path = cache / ".cache-index.json"
    cached_index = json.loads(index_path.read_text()) if index_path.is_file() else {}

    workers = min(8, max(2, os.cpu_count() or 4))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = dict(
            pool.map(
                build_deck,
                [(p, uncomp_dir, cache, public_static, pdftoppm, cwebp, cached_index.get(str(int(re.search(r"(\d+)", p.stem).group(1))))) for p in pdfs],
            )
        )

    # Remove stale static/<hash> dirs not referenced by current slides
    active_keys = {v["key"] for v in results.values()}
    for d in public_static.iterdir():
        if d.is_dir() and d.name not in active_keys:
            shutil.rmtree(d, ignore_errors=True)

    index_path.write_text(
        json.dumps(
            {
                k: {"key": v["key"], "pages": v["pages"], "size": v["size"], "mtime_ns": v["mtime_ns"], "recipe": RECIPE_TAG.decode()}
                for k, v in results.items()
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    public_map = {k: {"prefix": v["prefix"], "pdfUrl": v["pdfUrl"], "pages": v["pages"]} for k, v in sorted(results.items(), key=lambda x: int(x[0]))}
    out_json.write_text(json.dumps(public_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(public_map)} WebP slide decks -> {out_json}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
