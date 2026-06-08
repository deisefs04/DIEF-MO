"""ISA-Tab-aligned and FAIR-oriented exports for DIEF-MO.

This produces ISA-aligned tables (study/assay), a simplified investigation
file, and a FAIR/DataCite-style metadata record. It follows ISA-Tab
conventions but is NOT validated against the ISA specification by a certified
tool. For fully validated ISA output, the ``isatools`` package together with
proper ontology term sources (OBI, NCBITaxon, ...) would be used.
"""
import io
import json
import zipfile
from datetime import date

import pandas as pd

from . import db
from .datadict import DATA_DICTIONARY


def study_table(db_path=db.DB_PATH):
    """ISA study-level table: one row per registered sample."""
    samples = db.list_table("samples", db_path)
    matrices = {m["code"]: m for m in db.list_table("matrices", db_path)}
    batches = {b["code"]: b for b in db.list_table("batches", db_path)}
    experiments = {e["code"]: e for e in db.list_table("experiments", db_path)}
    rows = []
    for s in samples:
        b = batches.get(s["batch_code"], {})
        e = experiments.get(b.get("experiment_code"), {})
        m = matrices.get(s["matrix_code"], {})
        rows.append({
            "Source Name": b.get("experiment_code", ""),
            "Comment[Experiment Name]": e.get("name", ""),
            "Comment[Activity Type]": e.get("activity_code", ""),
            "Protocol REF": "sample collection",
            "Sample Name": s["code"],
            "Characteristics[Material Name]": m.get("name", ""),
            "Characteristics[Material Type]": m.get("matrix_type", ""),
            "Comment[Batch]": s["batch_code"],
        })
    return pd.DataFrame(rows)


def assay_table(db_path=db.DB_PATH):
    """ISA assay-level table: one row per sample-linked identifier.

    Directly generated IDs (with no registered sample) are intentionally
    excluded, since they have no study sample to anchor the assay graph.
    """
    rows = []
    for a in db.enriched_assays(db_path):
        if not a.get("sample_code"):
            continue
        rows.append({
            "Sample Name": a["sample_code"],
            "Comment[Replicate]": a.get("replicate_code") or "",
            "Protocol REF": "data acquisition",
            "Comment[Measurement Area]": a.get("area_name") or a["area_code"],
            "Assay Name": a["dief_id"],
            "Comment[DIEF-MO Identifier]": a["dief_id"],
            "Date": (a.get("created_at") or "")[:10],
        })
    return pd.DataFrame(rows)


def investigation_text(meta, experiments):
    """Simplified ISA i_investigation.txt content (tab-separated sections)."""
    ident = meta.get("identifier") or "DIEF-MO"
    title = meta.get("title") or "DIEF-MO Investigation"
    desc = meta.get("description") or ""
    today = date.today().isoformat()
    lines = [
        "ONTOLOGY SOURCE REFERENCE",
        "Term Source Name\t",
        "INVESTIGATION",
        f"Investigation Identifier\t{ident}",
        f"Investigation Title\t{title}",
        f"Investigation Description\t{desc}",
        "INVESTIGATION CONTACTS",
        f"Investigation Person Last Name\t{meta.get('contact_name', '')}",
        f"Investigation Person Email\t{meta.get('contact_email', '')}",
        "STUDY",
        f"Study Identifier\t{ident}-S1",
        f"Study Title\t{title}",
        f"Study Submission Date\t{today}",
        "Study File Name\ts_study.txt",
        "Study Assay File Name\ta_assay.txt",
        "STUDY DESIGN DESCRIPTORS",
        "Study Design Type\t" + "; ".join(e["code"] for e in experiments),
    ]
    return "\n".join(lines) + "\n"


def fair_record(meta, db_path=db.DB_PATH):
    """A FAIR/DataCite-style metadata record (JSON-serialisable)."""
    return {
        "identifier": meta.get("identifier") or "DIEF-MO",
        "title": meta.get("title") or "DIEF-MO dataset",
        "description": meta.get("description") or "",
        "creators": [meta["contact_name"]] if meta.get("contact_name") else [],
        "contact_email": meta.get("contact_email", ""),
        "keywords": [k.strip() for k in (meta.get("keywords") or "").split(",") if k.strip()],
        "license": meta.get("license") or "MIT",
        "identifier_scheme": "DIEF-MO (EXPERIMENT_AREA_MATRIX_SEQ)",
        "uses_controlled_vocabularies": True,
        "record_counts": db.counts(db_path),
        "data_dictionary": [
            {"column": col, "description": d, "type": t} for col, d, t in DATA_DICTIONARY
        ],
    }


FAIR_ALIGNMENT = [
    ("Findable", "Every assay has a unique, structured identifier; rich metadata and a data dictionary are exported."),
    ("Accessible", "Data and metadata are exported in open formats (CSV, TSV, JSON), with no proprietary lock-in."),
    ("Interoperable", "ISA-Tab-aligned study/assay tables and controlled vocabularies for areas, matrix types and activity."),
    ("Reusable", "Full provenance (sample -> batch -> experiment), an explicit license and documented fields."),
]


def build_bundle(meta, db_path=db.DB_PATH):
    """Return zip bytes with ISA-aligned files, the dataset and the FAIR record."""
    study = study_table(db_path)
    assay = assay_table(db_path)
    experiments = db.list_table("experiments", db_path)
    dataset = pd.DataFrame(db.enriched_assays(db_path))
    record = fair_record(meta, db_path)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("i_investigation.txt", investigation_text(meta, experiments))
        z.writestr("s_study.txt", study.to_csv(sep="\t", index=False))
        z.writestr("a_assay.txt", assay.to_csv(sep="\t", index=False))
        z.writestr("dief_dataset.csv", dataset.to_csv(index=False))
        z.writestr("fair_metadata.json", json.dumps(record, indent=2, ensure_ascii=False))
        z.writestr(
            "data_dictionary.csv",
            pd.DataFrame(DATA_DICTIONARY, columns=["column", "description", "type"]).to_csv(index=False),
        )
    return buf.getvalue()