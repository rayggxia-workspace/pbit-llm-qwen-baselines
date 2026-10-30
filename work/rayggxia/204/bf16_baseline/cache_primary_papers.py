"""Read-only literature acquisition and page rendering; not a circuit experiment."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import urllib.request
import pdfplumber

ROOT = Path(__file__).resolve().parents[4]
DEST = ROOT.parents[1] / "project_archives/matrix204_bf16_literature_20261028"
DEST.mkdir(parents=True, exist_ok=True)
PAPERS = [
    ("MFSA_2610.19645v1.pdf", "https://arxiv.org/pdf/2610.19645v1", 5),
    ("FlexBlock_author_2023.pdf", "https://jongse-park.github.io/files/paper/2023-tc-flexblock.pdf", 9),
]


def obtain(item):
    name, url, page = item
    path = DEST / name
    if not path.exists():
        request = urllib.request.Request(url, headers={"User-Agent": "BF16-baseline-literature-read/1.0"})
        data = urllib.request.urlopen(request, timeout=45).read()
        assert data.startswith(b"%PDF"), url
        path.write_bytes(data)
    row = {"name": name, "url": url, "path": str(path), "bytes": path.stat().st_size,
           "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "table_page_one_based": page + 1}
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[page].extract_text()
        assert "BF16" in text or "bfloat16" in text
        (DEST / (name + ".table.txt")).write_bytes((text + "\n").encode("utf-8"))
        png = DEST / (name + ".table.png")
        pdf.pages[page].to_image(resolution=120).save(str(png))
        row.update(table_text_sha256=hashlib.sha256((text + "\n").encode()).hexdigest(),
                   png_path=str(png), png_sha256=hashlib.sha256(png.read_bytes()).hexdigest(), pages=len(pdf.pages))
    return row


with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    rows = list(executor.map(obtain, PAPERS))
(DEST / "MANIFEST.json").write_bytes((json.dumps({"papers": rows, "new_simulations": 0}, ensure_ascii=False, indent=2) + "\n").encode())
print(json.dumps(rows, ensure_ascii=True, indent=2))
