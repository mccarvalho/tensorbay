"""Upload the TensorBay knowledge base to the private documents bucket.

    uv run --with boto3 --with pypdf --with python-docx python app/scripts/ingest_kb.py \
        "<path to KB TensorBay>" <bucket>

The bucket's default encryption (its own KMS key) applies; do not set SSE here.

Writes, under ``kb/``:
  templates/<NAME>.docx   the standard forms that are filled in, never rewritten by AI
  text/<name>.txt         plain text of every other allowed document (AI reference)
  manifest.json           what was uploaded

Left out on purpose: the Ascenty "Docs Ascenty ST IT" folder (bank statements, P&L),
the GPU demand spreadsheet, and anything about passports, EIN or LLC formation.
"""

import json
import sys
from pathlib import Path

import boto3
import docx
import pypdf
from docx.table import Table
from docx.text.paragraph import Paragraph

TEMPLATES = {
    "TensorBay_MSA_Standard_Form.docx": "MSA",
    "TensorBay_Multilateral_NDA_Standard.docx": "NDA",
    "TensorBay_Commercial_Partnership_Referral_Agreement_Standard.docx": "REFERRAL",
}
SKIP_DIRS = {"Docs Ascenty ST IT"}
SKIP_NAMES = {"TensorBay GPU Demand Summary.xlsx"}
SKIP_WORDS = ("passport", "ein", "llc formation", "formation")


def docx_text(path: Path) -> str:
    d = docx.Document(str(path))
    out: list[str] = []
    for el in d.element.body.iterchildren():
        if el.tag.endswith("}p"):
            out.append(Paragraph(el, d).text)
        elif el.tag.endswith("}tbl"):
            for row in Table(el, d).rows:
                cells: list[str] = []
                for c in row.cells:
                    if c.text not in cells:
                        cells.append(c.text)
                out.append(" | ".join(x.replace("\n", " / ") for x in cells))
    return "\n".join(out)


def pdf_text(path: Path) -> str:
    return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(str(path)).pages)


def main(kb: str, bucket: str) -> None:
    root = Path(kb)
    s3 = boto3.client("s3")
    manifest: dict[str, list[str]] = {"templates": [], "text": [], "skipped": []}
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.name.startswith("."):
            continue
        rel = f.relative_to(root)
        if SKIP_DIRS & set(rel.parts) or f.name in SKIP_NAMES or any(w in f.name.lower() for w in SKIP_WORDS):
            manifest["skipped"].append(str(rel))
            continue
        if f.name in TEMPLATES:
            key = f"kb/templates/{TEMPLATES[f.name]}.docx"
            s3.put_object(Bucket=bucket, Key=key, Body=f.read_bytes())
            manifest["templates"].append(key)
        if f.suffix == ".docx":
            text = docx_text(f)
        elif f.suffix == ".pdf":
            text = pdf_text(f)
        else:
            manifest["skipped"].append(str(rel))
            continue
        # The root copy and Contract/ copy of the AxeCompute MSA are identical.
        name = f.stem.replace(" ", "_")
        key = f"kb/text/{name}.txt"
        if key in manifest["text"]:
            continue
        s3.put_object(Bucket=bucket, Key=key, Body=text.encode(), ContentType="text/plain; charset=utf-8")
        manifest["text"].append(key)
        print(f"{len(text):>8}  {key}")
    s3.put_object(Bucket=bucket, Key="kb/manifest.json", Body=json.dumps(manifest, indent=1).encode(),)
    print(json.dumps({k: len(v) for k, v in manifest.items()}))
    print("skipped:", *manifest["skipped"], sep="\n  ")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
