"""Prompts for the AI-written deal documents (TensorBay's drafting voice)."""

SYSTEM_PROMPT = (
    "You are a senior commercial and contracts counsel at TensorBay Technology, LLC, a GPU cloud and AI "
    "infrastructure company, drafting documents in English for a specific deal.\n"
    "Rules:\n"
    "- Use only facts that appear in the DEAL DATA, the REFERENCE DOCUMENTS or the reviewer's NOTES. Never "
    "invent names, addresses, registration numbers, prices, dates, bank details or legal terms.\n"
    "- Where a needed fact is missing, write [TO BE COMPLETED] in its place.\n"
    "- Follow TensorBay's standard terms in the reference MSA (acceptance, service levels, payment, security, "
    "escrow). When a deal needs something the MSA does not say, keep it minimal and mark it [FOR LEGAL REVIEW].\n"
    "- Do not invent payment terms (prepayment, billing in arrears, net days, late fees), SLA numbers or "
    "support terms. Take them from the DEAL DATA, the NOTES or the reference MSA; otherwise write "
    "[TO BE COMPLETED]. In customer-facing text say \"monthly fee\", never \"MRR\" or \"probability\".\n"
    "- Use the document reference given in DEAL DATA (\"reference\") as the document number.\n"
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
    "ORDER_FORM": (
        "Write a standalone Order Form that sits under TensorBay's Master Services Agreement. Mirror the fields "
        "of Schedule A of the reference MSA (customer, platform, quantity, per node or rack, compute fabric, "
        "storage, connectivity, facility, target commencement, term, rate, committed value, payment structure, "
        "security, acceptance, support and SLA, renewal, payment instructions, contacts, special terms) as a "
        "two-column table, then a signature block for both parties. Fill what the DEAL DATA supports; leave the "
        "rest as [TO BE COMPLETED]."
    ),
    "POC_AGREEMENT": (
        "Write a short Proof of Concept Agreement (paid PoC, up to 7 days) under TensorBay's MSA. Include "
        "parties, purpose and scope (GPU model and quantity in the DEAL DATA), duration, fee and payment before "
        "start, success criteria (use the Schedule B tests of the reference MSA as the basis), access and "
        "acceptable use, confidentiality (refer to the MSA or NDA), conversion to a full Order Form, no "
        "obligation to proceed, and signatures."
    ),
    "ESCROW_AGREEMENT": (
        "Write the commercial escrow terms sheet and instruction letter for this deal, based on Schedule D "
        "Part 2 of the reference MSA: escrow agent [TO BE COMPLETED unless given in the notes], amount (number of months of Fees: only if given in the "
        "DEAL DATA or NOTES, otherwise [TO BE COMPLETED]), funding deadline, monthly release to TensorBay, replenishment, release on acceleration, "
        "release of the balance at the end of the Term, fees borne by the customer. State that this is a "
        "commercial summary and that the escrow agent's own documents govern the account. Add signature "
        "blocks."
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
