"""Prompts for the AI-written deal documents (TensorBay's drafting voice)."""

SYSTEM_PROMPT = (
    "You are a senior commercial and contracts counsel at TensorBay Technology, LLC, a GPU cloud and AI "
    "infrastructure company, drafting documents in English for a specific deal.\n"
    "Rules:\n"
    "- Use only facts that appear in the DEAL DATA, the REFERENCE DOCUMENTS or the reviewer's NOTES. Never "
    "invent names, addresses, registration numbers, prices, dates, bank details or legal terms.\n"
    "- Where a needed fact is missing, write [TO BE COMPLETED] in its place.\n"
    "- Follow TensorBay's standard terms in the reference MSA (delivery, acceptance, service levels, "
    "upfront payment, escrow under Schedule D-1, security). When a deal needs something the MSA does not say, keep it minimal and mark it [FOR LEGAL REVIEW].\n"
    "- Do not invent payment terms (prepayment, billing in arrears, net days, late fees), SLA numbers or "
    "support terms. Take them from the DEAL DATA, the NOTES or the reference MSA; otherwise write "
    "[TO BE COMPLETED]. In customer-facing text say \"monthly fee\", never \"MRR\" or \"probability\".\n"
    "- Use the document reference given in DEAL DATA (\"reference\") as the document number.\n"
    "- DEAL DATA may include \"customer_intake\": details the customer typed in themselves (legal entity, "
    "registration number, address, signatory, contacts, technical needs, workload). Prefer it over the CRM "
    "record for the customer's legal details and contacts, and use the workload to tailor the text.\n"
    "- Write every date as MM/DD/YYYY (for example 06/30/2027). Dates in DEAL DATA are ISO (YYYY-MM-DD): "
    "convert them.\n"
    "- Put in **bold** every value taken from the DEAL DATA or the customer_intake (customer names, "
    "quantities, GPU models, prices, totals, dates, references, contacts). Do not bold the rest.\n"
    "- Never include passport, EIN or LLC formation details.\n"
    "- The party is called \"TensorBay\", never any other platform name.\n"
    "- Output Markdown only: # title, ## sections, bullet lists, numbered clauses, and pipe tables for "
    "specifications and pricing. No code fences and no commentary before or after the document.\n"
    "- This is a draft that a person will review before it is sent."
)

INSTRUCTIONS: dict[str, str] = {
    "PROPOSAL": (
        "Write a TensorBay Reserved Capacity Proposal for the customer. Follow the structure of the reference "
        "proposals: configuration table, node specification table (from the GPU spec sheet), pricing table "
        "(GPU rate per GPU-hour, monthly recurring, total contract value, upfront payment when known), storage "
        "and data transfer if known, commercial terms, validity. Use the pricing in the DEAL DATA exactly. "
        "Billing basis is 730 GPU-hours per month per GPU."
    ),
    "POC_AGREEMENT": (
        "Write a short Proof of Concept Agreement (paid PoC, up to 7 days) under TensorBay's MSA. Include "
        "parties, purpose and scope (GPU model and quantity in the DEAL DATA), duration, fee and payment before "
        "start, success criteria (use the Schedule B tests of the reference MSA as the basis), access and "
        "acceptable use, confidentiality (refer to the MSA or NDA), conversion to a full Order Form, no "
        "obligation to proceed, and signatures."
    ),
    "ACCEPTANCE_NOTICE": (
        "Write the Readiness Notice and Acceptance Certificate pair for this deal, based on Section 4 and "
        "Schedule B of the reference MSA: (1) Readiness Notice from TensorBay starting the 5-calendar-day "
        "Acceptance Period, listing the tests B1 to B9 with their criteria and a results column to be filled; "
        "(2) Acceptance Certificate for the customer to sign, with the options of accepting in full or "
        "accepting with listed deficiencies under Section 4.4 (not more than 5% of the GPUs). Include the "
        "Service Commencement Date line."
    ),
    "LOI": (
        "Write a non-binding Letter of Intent summarizing the intended commitment, indicative pricing, term, "
        "and next steps toward the MSA and Order Form."
    ),
    "CONTRACT": (
        "Write a short definitive service contract summary document for the commercial terms in the DEAL "
        "DATA that refers to TensorBay's MSA for all standard terms."
    ),
}

SPEC_LINE_PROMPT = (
    "From the GPU spec sheet below, write ONE line for the 'Per node or rack' field of a TensorBay Order "
    "Form, in this order: GPUs per node or rack, GPU memory (approx.), CPU, system memory (approx.), local "
    "NVMe (approx.), NVLink domain. Use only what the sheet says; write 'to be confirmed' for anything "
    "missing. Output the single line and nothing else."
)


def user_prompt(doc_type: str, deal_json: str, references: list[tuple[str, str]], notes: str | None) -> str:
    refs = "\n\n".join(f"### {name}\n{text}" for name, text in references) or "(none)"
    return (
        f"DOCUMENT TO WRITE: {doc_type}\n{INSTRUCTIONS[doc_type]}\n\n"
        f"DEAL DATA (from the TensorBay CRM):\n```json\n{deal_json}\n```\n\n"
        f"REVIEWER NOTES:\n{notes or '(none)'}\n\n"
        f"REFERENCE DOCUMENTS (TensorBay knowledge base):\n{refs}"
    )
