"""TensorBay platform specifications, one entry per spec sheet in `KB TensorBay/GPU-Specs`.

The Order Form and the MSA (Schedule A) are filled from here, not from a model: the numbers are those of
the spec sheet and nothing else. `tests/test_gpu_specs.py` compares every figure with the PDFs.
Platforms without a sheet (for example GB300) are not listed: the caller falls back to the old path.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    sheet: str                    # file name stem of the spec sheet PDF
    form_label: str | None        # tick box on the Order Form; None = "Other: <name>"
    name: str                     # used in "Other: ..." and in lines
    unit: str                     # "node" | "rack"
    gpus_per_unit: int
    gpu_line: str                 # e.g. "180 GB HBM3e each"
    cpus_per_unit: int
    cpu_line: str
    system_memory: str
    local_storage: str
    nvlink: str
    fabric: str                   # "INFINIBAND" | "ROCE"
    fabric_rate: str              # shown after "approx."
    local_nvme_tb: int | None = None

    def per_unit_line(self) -> str:
        return (
            f"{self.gpus_per_unit} GPUs per {self.unit}, approx. {self.gpu_line}, "
            f"{self.cpu_line}, approx. {self.system_memory}, {self.local_storage}, {self.nvlink}."
        )


_EPYC9005 = "2 AMD EPYC 9005 Series CPUs, up to 64 cores each"
_HGX_STORAGE = "local NVMe 8 x 3.5 TB (28 TB, approx.)"

SPECS: dict[str, PlatformSpec] = {s.key: s for s in (
    PlatformSpec(
        "GB200", "TensorBay_Spec_NVIDIA_GB200_NVL72", "NVIDIA GB200 NVL72", "NVIDIA GB200 NVL72", "rack", 72,
        "186 GB HBM3e per GPU (13.4 TB per rack)", 36,
        "36 NVIDIA Grace CPUs, 72 Arm Neoverse V2 cores each (2,592 cores)", "17 TB LPDDR5X",
        "NVMe local storage per compute tray plus shared storage", "1 NVLink domain (72 GPUs)",
        "INFINIBAND", "400 Gb/s per GPU"),
    PlatformSpec(
        "VR200", "TensorBay_Spec_NVIDIA_DGX_VR200", "NVIDIA DGX VR200", "NVIDIA DGX VR200", "node", 8,
        "288 GB HBM4 per GPU (2.3 TB per node)", 2, "2 NVIDIA Vera CPUs, 88 Arm cores each (176 cores)",
        "up to 3 TB LPDDR5X", "local NVMe 8 x 3.5 TB (28 TB, approx.)", "1 NVLink 6 domain (8 GPUs)",
        "ROCE", "1.6 Tb/s per GPU", 28),
    PlatformSpec(
        "B300LIQ", "TensorBay_Spec_NVIDIA_HGX_B300_Liquid-Cooled", "NVIDIA HGX B300 (liquid-cooled)",
        "NVIDIA HGX B300 (liquid-cooled)", "node", 8, "288 GB HBM3e per GPU (2.3 TB per node)", 2, _EPYC9005,
        "up to 3 TB DDR5", _HGX_STORAGE, "1 NVLink domain (8 GPUs)", "ROCE", "800 Gb/s per GPU", 28),
    PlatformSpec(
        "B300", "TensorBay_Spec_NVIDIA_HGX_B300_Air-Cooled", "NVIDIA HGX B300 (air-cooled)",
        "NVIDIA HGX B300 (air-cooled)", "node", 8, "288 GB HBM3e per GPU (2.3 TB per node)", 2, _EPYC9005,
        "up to 3 TB DDR5", _HGX_STORAGE, "1 NVLink domain (8 GPUs)", "ROCE", "800 Gb/s per GPU", 28),
    PlatformSpec(
        "B200", "TensorBay_Spec_NVIDIA_HGX_B200", "NVIDIA HGX B200", "NVIDIA HGX B200", "node", 8,
        "180 GB HBM3e per GPU (1.4 TB per node)", 2, _EPYC9005, "up to 3 TB DDR5", _HGX_STORAGE,
        "1 NVLink domain (8 GPUs)", "ROCE", "400 Gb/s per GPU", 28),
    PlatformSpec(
        "A100", "TensorBay_Spec_NVIDIA_HGX_A100_SXM", None, "NVIDIA HGX A100 (SXM 80 GB)", "node", 8,
        "80 GB HBM2e per GPU (640 GB per node)", 2, "2 AMD EPYC 7003/9004 Series CPUs, up to 64 cores each",
        "up to 2 TB DDR4/DDR5", _HGX_STORAGE, "1 NVLink domain (8 GPUs)", "ROCE", "200 Gb/s per GPU", 28),
    PlatformSpec(
        "RTX6000", "TensorBay_Spec_NVIDIA_RTX_PRO_6000_Blackwell_Server", None,
        "NVIDIA RTX PRO 6000 Blackwell Server Edition", "node", 8, "96 GB GDDR7 per GPU (768 GB per node)", 2,
        _EPYC9005, "up to 1.5 TB DDR5", _HGX_STORAGE, "PCIe Gen5 x16 per GPU (no NVLink)", "ROCE",
        "400 Gb/s per GPU pair", 28),
)}


def lookup(gpu_model: str | None) -> PlatformSpec | None:
    m = (gpu_model or "").upper().replace(" ", "").replace("-", "").replace("_", "")
    if not m:
        return None
    if "GB300" in m:
        return None  # no spec sheet yet
    if "GB200" in m or "NVL72" in m:
        return SPECS["GB200"]
    if "VR200" in m or "VERARUBIN" in m:
        return SPECS["VR200"]
    if "B300" in m:
        return SPECS["B300LIQ"] if ("LIQUID" in m or "DLC" in m) else SPECS["B300"]
    if "B200" in m:
        return SPECS["B200"]
    if "A100" in m:
        return SPECS["A100"]
    if "RTX" in m or "6000" in m:
        return SPECS["RTX6000"]
    return None
