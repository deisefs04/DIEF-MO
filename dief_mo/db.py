"""SQLite persistence for DIEF-MO master data, secondary entities and assays.

Core entities:        areas, matrices, experiments
Secondary (lineage):  batches (-> experiment), samples (-> batch, matrix),
                      replicates (-> sample). The SEQ index of an identifier
                      is the poster's "Sequence" entity.
Generated:            assays (the DIEF-MO identifiers, optionally linked to a
                      sample and/or replicate)
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .encoder import generate_id

DB_PATH = Path(__file__).resolve().parent.parent / "dief_mo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS areas (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT
);
CREATE TABLE IF NOT EXISTS matrices (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, matrix_type TEXT
);
CREATE TABLE IF NOT EXISTS experiments (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, activity_code TEXT
);
CREATE TABLE IF NOT EXISTS batches (
    code TEXT PRIMARY KEY, experiment_code TEXT NOT NULL,
    name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS samples (
    code TEXT PRIMARY KEY, batch_code TEXT NOT NULL, matrix_code TEXT NOT NULL,
    name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS replicates (
    code TEXT PRIMARY KEY, sample_code TEXT NOT NULL,
    name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assays (
    dief_id TEXT PRIMARY KEY, experiment_code TEXT NOT NULL,
    area_code TEXT NOT NULL, matrix_code TEXT NOT NULL,
    seq INTEGER NOT NULL, created_at TEXT NOT NULL
);
"""

_KEYED_TABLES = {"areas", "matrices", "experiments", "batches", "samples", "replicates"}
_ALLOWED_TABLES = _KEYED_TABLES | {"assays"}
_EDITABLE_COLUMNS = {"name", "description", "matrix_type", "activity_code"}


@contextmanager
def get_conn(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path=DB_PATH):
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)
        # Migrations for older databases: add nullable lineage columns to assays.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(assays)").fetchall()]
        if "sample_code" not in cols:
            conn.execute("ALTER TABLE assays ADD COLUMN sample_code TEXT")
        if "replicate_code" not in cols:
            conn.execute("ALTER TABLE assays ADD COLUMN replicate_code TEXT")


# --- generic helpers -----------------------------------------------------
def get_row(table, code, db_path=DB_PATH):
    if table not in _KEYED_TABLES:
        raise ValueError(f"Tabela desconhecida: {table}")
    with get_conn(db_path) as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE code = ?", (code.strip(),)).fetchone()
    return dict(row) if row else None


def code_exists(table, code, db_path=DB_PATH):
    return get_row(table, code, db_path) is not None


def delete_row(table, code, db_path=DB_PATH):
    if table not in _KEYED_TABLES:
        raise ValueError(f"Tabela desconhecida: {table}")
    with get_conn(db_path) as conn:
        conn.execute(f"DELETE FROM {table} WHERE code = ?", (code.strip(),))


def update_fields(table, code, fields, db_path=DB_PATH):
    """Update editable descriptive fields, preserving code, FKs and created_at."""
    if table not in _KEYED_TABLES:
        raise ValueError(f"Tabela desconhecida: {table}")
    cols = [c for c in fields if c in _EDITABLE_COLUMNS]
    if not cols:
        return
    set_clause = ", ".join(f"{c} = ?" for c in cols)
    values = [(fields[c] or "").strip() for c in cols] + [code.strip()]
    with get_conn(db_path) as conn:
        conn.execute(f"UPDATE {table} SET {set_clause} WHERE code = ?", values)


def list_table(table, db_path=DB_PATH):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Tabela desconhecida: {table}")
    order = "created_at DESC" if table == "assays" else "code"
    with get_conn(db_path) as conn:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
    return [dict(r) for r in rows]


# --- core master data ----------------------------------------------------
def add_area(code, name, description="", db_path=DB_PATH):
    with get_conn(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO areas(code, name, description) VALUES (?, ?, ?)",
                     (code.strip(), name.strip(), (description or "").strip()))


def add_matrix(code, name, matrix_type="", db_path=DB_PATH):
    with get_conn(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO matrices(code, name, matrix_type) VALUES (?, ?, ?)",
                     (code.strip(), name.strip(), (matrix_type or "").strip()))


def add_experiment(code, name, activity_code="", db_path=DB_PATH):
    with get_conn(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO experiments(code, name, activity_code) VALUES (?, ?, ?)",
                     (code.strip(), name.strip(), (activity_code or "").strip()))


# --- secondary entities (lineage) ---------------------------------------
def add_batch(code, experiment_code, name, db_path=DB_PATH):
    if not code_exists("experiments", experiment_code, db_path):
        raise ValueError(f"Experiment '{experiment_code}' is not registered.")
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO batches(code, experiment_code, name, created_at) VALUES (?, ?, ?, ?)",
            (code.strip(), experiment_code.strip(), name.strip(), _now()))


def add_sample(code, batch_code, matrix_code, name, db_path=DB_PATH):
    if not code_exists("batches", batch_code, db_path):
        raise ValueError(f"Batch '{batch_code}' is not registered.")
    if not code_exists("matrices", matrix_code, db_path):
        raise ValueError(f"Matrix '{matrix_code}' is not registered.")
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO samples(code, batch_code, matrix_code, name, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (code.strip(), batch_code.strip(), matrix_code.strip(), name.strip(), _now()))


def add_replicate(code, sample_code, name, db_path=DB_PATH):
    if not code_exists("samples", sample_code, db_path):
        raise ValueError(f"Sample '{sample_code}' is not registered.")
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO replicates(code, sample_code, name, created_at) VALUES (?, ?, ?, ?)",
            (code.strip(), sample_code.strip(), name.strip(), _now()))


# --- ID generation with lineage -----------------------------------------
def _next_seq(conn, experiment, area, matrix):
    row = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 AS nxt FROM assays "
        "WHERE experiment_code = ? AND area_code = ? AND matrix_code = ?",
        (experiment, area, matrix)).fetchone()
    return row["nxt"]


def create_assay(experiment, area, matrix, sample_code=None, replicate_code=None, db_path=DB_PATH):
    """Generate and persist a new assay ID, auto-incrementing the SEQ index
    per (experiment, area, matrix) combination."""
    with get_conn(db_path) as conn:
        seq = _next_seq(conn, experiment, area, matrix)
        dief_id = generate_id(experiment, area, matrix, seq)
        conn.execute(
            "INSERT INTO assays(dief_id, experiment_code, area_code, matrix_code, seq, "
            "created_at, sample_code, replicate_code) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (dief_id, experiment, area, matrix, seq, _now(), sample_code, replicate_code))
    return dief_id


def create_assay_from_sample(sample_code, area, db_path=DB_PATH):
    """Generate an ID for a sample, deriving experiment and matrix from its
    lineage (sample -> batch -> experiment, sample -> matrix)."""
    sample = get_row("samples", sample_code, db_path)
    if not sample:
        raise ValueError(f"Sample '{sample_code}' is not registered.")
    batch = get_row("batches", sample["batch_code"], db_path)
    if not batch:
        raise ValueError(f"Sample's batch '{sample['batch_code']}' is missing.")
    return create_assay(batch["experiment_code"], area, sample["matrix_code"],
                        sample_code=sample_code, db_path=db_path)


def create_assay_from_replicate(replicate_code, area, db_path=DB_PATH):
    """Generate an ID for a replicate, deriving the full chain
    (replicate -> sample -> batch -> experiment, sample -> matrix)."""
    replicate = get_row("replicates", replicate_code, db_path)
    if not replicate:
        raise ValueError(f"Replicate '{replicate_code}' is not registered.")
    sample = get_row("samples", replicate["sample_code"], db_path)
    if not sample:
        raise ValueError(f"Replicate's sample '{replicate['sample_code']}' is missing.")
    batch = get_row("batches", sample["batch_code"], db_path)
    if not batch:
        raise ValueError(f"Sample's batch '{sample['batch_code']}' is missing.")
    return create_assay(batch["experiment_code"], area, sample["matrix_code"],
                        sample_code=sample["code"], replicate_code=replicate_code, db_path=db_path)


# --- reporting / lineage / quality --------------------------------------
def enriched_assays(db_path=DB_PATH):
    """One row per identifier with full resolved metadata and lineage."""
    sql = """
        SELECT a.dief_id, a.experiment_code, e.name AS experiment_name, e.activity_code,
               a.area_code, ar.name AS area_name,
               a.matrix_code, m.name AS matrix_name, m.matrix_type,
               a.sample_code, s.name AS sample_name,
               a.replicate_code, rp.name AS replicate_name,
               s.batch_code, b.name AS batch_name,
               a.seq, a.created_at
        FROM assays a
        LEFT JOIN experiments e ON e.code = a.experiment_code
        LEFT JOIN areas       ar ON ar.code = a.area_code
        LEFT JOIN matrices    m ON m.code = a.matrix_code
        LEFT JOIN samples     s ON s.code = a.sample_code
        LEFT JOIN replicates  rp ON rp.code = a.replicate_code
        LEFT JOIN batches     b ON b.code = s.batch_code
        ORDER BY a.created_at DESC
    """
    with get_conn(db_path) as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def get_lineage(dief_id, db_path=DB_PATH):
    for r in enriched_assays(db_path):
        if r["dief_id"] == dief_id:
            return r
    return None


def experiment_tree(db_path=DB_PATH):
    """Nested view: experiment -> batches -> samples -> (replicates, assays)."""
    experiments = list_table("experiments", db_path)
    batches = list_table("batches", db_path)
    samples = list_table("samples", db_path)
    replicates = list_table("replicates", db_path)
    assays = list_table("assays", db_path)
    tree = []
    for e in experiments:
        e_node = {"experiment": e, "batches": []}
        for b in [b for b in batches if b["experiment_code"] == e["code"]]:
            b_node = {"batch": b, "samples": []}
            for s in [s for s in samples if s["batch_code"] == b["code"]]:
                s_reps = [r for r in replicates if r["sample_code"] == s["code"]]
                s_assays = [a for a in assays if a.get("sample_code") == s["code"]]
                b_node["samples"].append({"sample": s, "replicates": s_reps, "assays": s_assays})
            e_node["batches"].append(b_node)
        tree.append(e_node)
    return tree


def counts(db_path=DB_PATH):
    with get_conn(db_path) as conn:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("areas", "matrices", "experiments", "batches",
                          "samples", "replicates", "assays")}


def quality_report(db_path=DB_PATH):
    exps = list_table("experiments", db_path)
    matrices = list_table("matrices", db_path)
    batches = list_table("batches", db_path)
    samples = list_table("samples", db_path)
    replicates = list_table("replicates", db_path)
    assays = list_table("assays", db_path)

    exp_codes = {e["code"] for e in exps}
    matrix_codes = {m["code"] for m in matrices}
    batch_codes = {b["code"] for b in batches}
    sample_codes = {s["code"] for s in samples}
    exp_with_batch = {b["experiment_code"] for b in batches}
    batch_with_sample = {s["batch_code"] for s in samples}
    sample_with_assay = {a.get("sample_code") for a in assays if a.get("sample_code")}
    rep_with_assay = {a.get("replicate_code") for a in assays if a.get("replicate_code")}

    samples_with_assay_count = len([s for s in samples if s["code"] in sample_with_assay])
    return {
        "experiments_without_batches": sorted(exp_codes - exp_with_batch),
        "batches_without_samples": sorted(batch_codes - batch_with_sample),
        "samples_without_assays": sorted(s["code"] for s in samples if s["code"] not in sample_with_assay),
        "replicates_without_assays": sorted(r["code"] for r in replicates if r["code"] not in rep_with_assay),
        "orphan_batches": sorted(b["code"] for b in batches if b["experiment_code"] not in exp_codes),
        "orphan_samples": sorted(
            s["code"] for s in samples
            if s["batch_code"] not in batch_codes or s["matrix_code"] not in matrix_codes),
        "orphan_replicates": sorted(r["code"] for r in replicates if r["sample_code"] not in sample_codes),
        "direct_assays": sorted(a["dief_id"] for a in assays if not a.get("sample_code")),
        "sample_coverage": (samples_with_assay_count / len(samples)) if samples else None,
    }


# --- demo helpers --------------------------------------------------------
def clear_all(db_path=DB_PATH):
    """Delete every record from all tables (does not drop the schema)."""
    with get_conn(db_path) as conn:
        for t in ("assays", "replicates", "samples", "batches",
                  "experiments", "matrices", "areas"):
            conn.execute(f"DELETE FROM {t}")


def seed_demo(db_path=DB_PATH):
    """Reset the database to a small, illustrative example dataset that
    exercises every page (lineage, replicates, quality, ISA, activity filter)."""
    clear_all(db_path)
    add_area("PRO", "Proteomics", "Protein-level analyses", db_path=db_path)
    add_area("GEN", "Genomics", "DNA-level analyses", db_path=db_path)
    add_matrix("M001", "E. coli culture", "Bacterial culture", db_path=db_path)
    add_matrix("M002", "Yeast culture", "Fungal culture", db_path=db_path)
    add_experiment("E001", "Pilot proteomics study", "E", db_path=db_path)
    add_experiment("E002", "Literature survey", "L", db_path=db_path)
    add_batch("B001", "E001", "First experimental batch", db_path=db_path)
    add_batch("B002", "E002", "Literature-derived batch", db_path=db_path)
    add_sample("S001", "B001", "M001", "Sample 1 - E. coli", db_path=db_path)
    add_sample("S002", "B001", "M002", "Sample 2 - Yeast", db_path=db_path)
    add_sample("S003", "B002", "M001", "Sample 3 - literature E. coli", db_path=db_path)
    add_replicate("R001", "S001", "Replicate 1 of S001", db_path=db_path)
    add_replicate("R002", "S001", "Replicate 2 of S001", db_path=db_path)
    add_replicate("R003", "S002", "Replicate 1 of S002", db_path=db_path)
    create_assay_from_replicate("R001", "PRO", db_path=db_path)
    create_assay_from_replicate("R002", "PRO", db_path=db_path)
    create_assay_from_sample("S002", "GEN", db_path=db_path)
    create_assay_from_replicate("R003", "GEN", db_path=db_path)
    create_assay_from_sample("S003", "PRO", db_path=db_path)
    create_assay("E001", "PRO", "M001", db_path=db_path)  # a direct ID (no sample)