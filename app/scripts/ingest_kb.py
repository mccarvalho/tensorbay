"""Upload the TensorBay knowledge base to the private documents bucket.

    uv run --with boto3 --with pypdf --with python-docx python app/scripts/ingest_kb.py \
        "<path to KB TensorBay>" <bucket> ["<path to the contract package, e.g. TensorBay_Contract_Package_V4>"]

The contract package (01 MSA, 02 Schedule A Order Form, 03 Schedule D-1 Escrow Agreement) is the
current standard: it is uploaded last, so it replaces the older MSA form that still sits in the KB.

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


# Contract package files (by numeric prefix) -> template name and reference text name.
PACKAGE = {
    "01": ("MSA", "TensorBay_MSA_Standard_Form"),
    "02": ("ORDER_FORM", "TensorBay_Schedule_A_Order_Form"),
    "03": ("ESCROW", "TensorBay_Schedule_D1_Escrow_Agreement"),
}


def upload_package(s3, package: str, bucket: str, manifest: dict) -> None:
    for f in sorted(Path(package).glob("*.docx")):
        entry = PACKAGE.get(f.name[:2])
        if not entry:
            continue
        template, text_name = entry
        s3.put_object(Bucket=bucket, Key=f"kb/templates/{template}.docx", Body=f.read_bytes())
        text = docx_text(f)
        s3.put_object(Bucket=bucket, Key=f"kb/text/{text_name}.txt", Body=text.encode(), ContentType="text/plain; charset=utf-8")
        manifest.setdefault("package", []).append(f.name)
        print(f"{len(text):>8}  package {f.name} -> templates/{template}.docx + text/{text_name}.txt")


def main(kb: str, bucket: str, package: str | None = None) -> None:
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
    if package:
        upload_package(s3, package, bucket, manifest)
    s3.put_object(Bucket=bucket, Key="kb/manifest.json", Body=json.dumps(manifest, indent=1).encode(),)
    print(json.dumps({k: len(v) for k, v in manifest.items()}))
    print("skipped:", *manifest["skipped"], sep="\n  ")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
