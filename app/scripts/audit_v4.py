"""Audit generated documents against their V4 originals: structure, every text difference, formatting, dates.

    uv run --with python-docx python app/scripts/audit_v4.py <generated MSA.docx> <generated Order Form.docx> <generated Escrow.docx>

The originals are read from ~/Downloads/TensorBay_Contract_Package_V4 (edit P below if they live elsewhere).
"""
import io, re, sys, zipfile, docx
from docx.table import Table
from docx.text.paragraph import Paragraph

def blocks(d):
    """Ordered list of ('p', idx, text, style, runfmt) and ('c', table, row, col, text) for body + tables."""
    out=[]
    for pi,p in enumerate(d.paragraphs):
        out.append(("P",pi,p.text,p.style.name,[(r.bold,r.italic,r.font.size,r.font.name) for r in p.runs][:1]))
    for ti,t in enumerate(d.tables):
        for ri,r in enumerate(t.rows):
            seen=set()
            for ci,c in enumerate(r.cells):
                if id(c._tc) in seen: continue
                seen.add(id(c._tc))
                for pj,p in enumerate(c.paragraphs):
                    out.append(("C",(ti,ri,ci,pj),p.text,p.style.name,[(x.bold,x.italic,x.font.size,x.font.name) for x in p.runs][:1]))
    return out

def audit(name, orig_path, gen_path, expect_changed_substr=()):
    o=docx.Document(orig_path); g=docx.Document(gen_path)
    print("\n"+"="*100); print(name)
    # 1 structure
    s=[("paragraphs",len(o.paragraphs),len(g.paragraphs)),("tables",len(o.tables),len(g.tables)),("sections",len(o.sections),len(g.sections))]
    for a,b in zip(o.tables,g.tables): s.append(("table rows x cols",(len(a.rows),len(a.columns)),(len(b.rows),len(b.columns))))
    bad=[x for x in s if x[1]!=x[2]]
    print("STRUCTURE:", "identical" if not bad else bad)
    print("HEADER/FOOTER:", "identical" if [p.text for sec in o.sections for p in sec.header.paragraphs+sec.footer.paragraphs]==[p.text for sec in g.sections for p in sec.header.paragraphs+sec.footer.paragraphs] else "DIFFERENT")
    # 2 text + format diffs
    bo,bg=blocks(o),blocks(g)
    assert len(bo)==len(bg), (len(bo),len(bg))
    changed=[];fmt=[];style=[]
    for a,b in zip(bo,bg):
        if a[2]!=b[2]: changed.append((a,b))
        if a[3]!=b[3]: style.append((a,b))
        if a[4]!=b[4] and a[2]!="" : fmt.append((a,b))
    total=len(bo); print(f"BLOCKS: {total}; changed text: {len(changed)}; style changes: {len(style)}; first-run formatting changes: {len(fmt)}")
    for a,b in fmt[:6]: print("  FORMAT DIFF", a[1], a[4], "->", b[4], "|", b[2][:60])
    # which parts of the legal body changed? (paragraphs outside tables)
    print("\nCHANGED TEXT (original -> generated):")
    for a,b in changed:
        where=f"para {a[1]}" if a[0]=="P" else f"table {a[1][0]} r{a[1][1]} c{a[1][2]}"
        # show only the differing window
        x,y=a[2],b[2]; i=0
        while i<min(len(x),len(y)) and x[i]==y[i]: i+=1
        j=0
        while j<min(len(x),len(y))-i and x[-1-j]==y[-1-j]: j+=1
        print(f"  [{where}] …{x[max(0,i-25):len(x)-j][:150]!r}  ->  …{y[max(0,i-25):len(y)-j][:150]!r}")
    # 3 hygiene on the generated text
    txt="\n".join(b[2] for b in bg)
    print("\nHYGIENE:")
    for label,pat in (("raw ISO dates",r"\b20\d\d-\d\d-\d\d\b"),("DD / MM / YYYY blanks filled wrongly",r"\b\d\d / \d\d / \d{4}\b"),("python leftovers",r"(?<!☐ )(?<!☒ )\bNone\b(?! +☐)|undefined|\{kind\}|\{\w+\}|\bnan\b"),("double spaces in changed cells",None)):
        if pat is None:
            hits=[b[2][:80] for a,b in changed if "  " in b[2].replace("  Order Effective","").replace("   ☐","").replace("  |","")][:3]
        else: hits=re.findall(pat,txt)[:5]
        print(f"  {label}: {'none' if not hits else hits}")
    dates=sorted(set(re.findall(r"\b\d{2}/\d{2}/\d{4}\b",txt))); print("  dates found (MM/DD/YYYY):",dates)
    unreplaced=sorted(set(re.findall(r"\[[A-Za-z ●,]{3,45}\]",txt)))
    print("  bracketed placeholders still present:",unreplaced[:10])
    return g,txt

if __name__=="__main__":
    P="/Users/mauriciodecarvalho/Downloads/TensorBay_Contract_Package_V4/"
    for name,orig,gen in (("MSA",P+"01_TensorBay_MSA_Standard_Form.docx",sys.argv[1]),("ORDER FORM",P+"02_TensorBay_Schedule_A_Order_Form.docx",sys.argv[2]),("ESCROW",P+"03_TensorBay_Schedule_D1_Escrow_Agreement.docx",sys.argv[3])):
        audit(name,orig,gen)
