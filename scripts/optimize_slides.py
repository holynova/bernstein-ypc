#!/usr/bin/env python3
"""Render verified deck pages and package them as web-sized JPEGs.

Keeps unmodified original PDF in work/slides/<stem>-uncompressed.pdf and writes
a size-optimized PDF for web download only when smaller than the original.
"""
import io
import pathlib
import shutil
import subprocess
import sys
import tempfile
from PIL import Image
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

POPPLER_BIN = "/Users/sym/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm"


def find_pdftoppm():
    if pathlib.Path(POPPLER_BIN).is_file():
        return POPPLER_BIN
    found = shutil.which("pdftoppm")
    if not found:
        raise RuntimeError("pdftoppm not found")
    return found


def optimize_pdf(source: pathlib.Path):
    root = pathlib.Path(__file__).resolve().parents[1]
    uncomp_dir = root / "work/slides"
    uncomp_dir.mkdir(parents=True, exist_ok=True)
    original = uncomp_dir / f"{source.stem}-uncompressed.pdf"
    if not original.exists():
        shutil.copyfile(source, original)

    reader = PdfReader(original)
    target = source.with_suffix(".optimized.pdf")
    pdf = canvas.Canvas(str(target), pagesize=(1376, 768), pageCompression=1)
    pdf.setTitle(f"{source.stem} · 伯恩斯坦《青少年音乐会》幻灯片")
    pdftoppm = find_pdftoppm()

    with tempfile.TemporaryDirectory(dir=uncomp_dir) as tmpdir:
        for i, page in enumerate(reader.pages):
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            prefix = pathlib.Path(tmpdir) / "page"
            subprocess.run(
                [
                    pdftoppm,
                    "-f",
                    str(i + 1),
                    "-l",
                    str(i + 1),
                    "-singlefile",
                    "-scale-to",
                    str(round(max(width, height))),
                    "-png",
                    str(original),
                    str(prefix),
                ],
                check=True,
            )
            with Image.open(prefix.with_suffix(".png")) as img:
                buf = io.BytesIO()
                img.convert("RGB").save(buf, "JPEG", quality=95, subsampling=0)
                buf.seek(0)
                pdf.setPageSize((width, height))
                pdf.drawImage(ImageReader(buf), 0, 0, width=width, height=height)
                pdf.showPage()
    pdf.save()

    if len(PdfReader(target).pages) != len(reader.pages):
        target.unlink(missing_ok=True)
        raise RuntimeError("Page count changed during PDF optimization")

    if target.stat().st_size < original.stat().st_size:
        target.replace(source)
    else:
        shutil.copyfile(original, source)
        target.unlink(missing_ok=True)
    print(f"Web PDF: {source.name}: {original.stat().st_size / 1e6:.2f} -> {source.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    optimize_pdf(pathlib.Path(sys.argv[1]))
