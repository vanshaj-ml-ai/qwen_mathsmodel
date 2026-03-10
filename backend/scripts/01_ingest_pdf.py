import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

import json
from pathlib import Path
import fitz
from tqdm import tqdm

from rag.config import RAW_DIR, OCR_DIR, PAGES_DIR
from rag.ocr import ocr_image
from rag.ingest_utils import has_meaningful_text, extract_text_layer, render_page_to_png, cleanup_text

def main():
    pdf_path = next(RAW_DIR.glob("*.pdf"), None)
    if not pdf_path:
        raise SystemExit("Put your PDF in backend/data/raw/ as .pdf")

    OCR_DIR.mkdir(parents=True, exist_ok=True)
    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    print("PDF:", pdf_path.name)
    print("Pages:", doc.page_count)

    for i in tqdm(range(doc.page_count), desc="Ingest"):
        page_no = i + 1
        out_json = OCR_DIR / f"page_{page_no:04d}.json"
        if out_json.exists():
            continue  # resume support

        page = doc.load_page(i)

        if has_meaningful_text(page):
            text = cleanup_text(extract_text_layer(page))
            payload = {"page": page_no, "mode": "text_layer", "text": text}
            out_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            continue

        img_path = PAGES_DIR / f"page_{page_no:04d}.png"
        render_page_to_png(page, img_path)

        text = cleanup_text(ocr_image(str(img_path)))
        payload = {"page": page_no, "mode": "ocr", "text": text}
        out_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    main()
