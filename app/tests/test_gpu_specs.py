"""gpu_specs.py against the real spec sheets (confidential: set TB_GPU_SPECS to the GPU-Specs folder)."""
import os
import re
from pathlib import Path

import pytest

from neocloud.domains.documents import gpu_specs

DIR = os.environ.get("TB_GPU_SPECS")


def test_lookup_maps_the_names_used_in_the_crm():
    assert gpu_specs.lookup("GB200").key == "GB200" and gpu_specs.lookup("GB200 NVL72").gpus_per_unit == 72
    assert gpu_specs.lookup("B300").key == "B300" and gpu_specs.lookup("B300 liquid-cooled").key == "B300LIQ"
    assert gpu_specs.lookup("HGX B200").key == "B200" and gpu_specs.lookup("A100 80GB").key == "A100"
    assert gpu_specs.lookup("RTX PRO 6000").key == "RTX6000" and gpu_specs.lookup("VR200").key == "VR200"
    assert gpu_specs.lookup("GB300") is None and gpu_specs.lookup("H200") is None and gpu_specs.lookup("") is None


@pytest.mark.skipif(not DIR or not Path(DIR).is_dir(), reason="TB_GPU_SPECS not set")
@pytest.mark.parametrize("spec", list(gpu_specs.SPECS.values()), ids=lambda s: s.key)
def test_every_figure_is_on_the_spec_sheet(spec):
    from pypdf import PdfReader

    text = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(Path(DIR) / f"{spec.sheet}.pdf").pages)
    line = " ".join([spec.gpu_line, spec.cpu_line, spec.system_memory, spec.local_storage, spec.nvlink, spec.fabric_rate])
    for num in re.findall(r"\d[\d,.]*", line):
        num = num.rstrip(".,")
        # the sheets write the same figures a little differently ("1.6 Tb/s", "28 TB", "2,592")
        assert num in text or num.replace(",", "") in text, f"{spec.key}: {num} is not on {spec.sheet}.pdf"
    assert f"{spec.gpus_per_unit} x" in text or f"{spec.gpus_per_unit} " in text
