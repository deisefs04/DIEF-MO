import os
import sqlite3
import tempfile

import pytest

from dief_mo import db


@pytest.fixture
def temp_db():
    path = os.path.join(tempfile.mkdtemp(), "t.db")
    db.init_db(path)
    return path


def _seed(path):
    db.add_area("PRO", "Proteomics", db_path=path)
    db.add_matrix("M001", "E. coli", "Bacterial culture", db_path=path)
    db.add_experiment("E001", "Pilot", "EXP", db_path=path)
    db.add_batch("B001", "E001", "First batch", db_path=path)
    db.add_sample("S001", "B001", "M001", "Sample 1", db_path=path)


def test_generate_from_sample_derives_lineage(temp_db):
    _seed(temp_db)
    dief_id = db.create_assay_from_sample("S001", "PRO", db_path=temp_db)
    assert dief_id == "E001_PRO_M001_001"
    info = db.get_lineage(dief_id, db_path=temp_db)
    assert info["sample_code"] == "S001"
    assert info["batch_code"] == "B001"
    assert info["experiment_code"] == "E001"
    assert info["matrix_code"] == "M001"


def test_generate_from_replicate_derives_full_chain(temp_db):
    _seed(temp_db)
    db.add_replicate("R001", "S001", "Replicate 1", db_path=temp_db)
    dief_id = db.create_assay_from_replicate("R001", "PRO", db_path=temp_db)
    assert dief_id == "E001_PRO_M001_001"
    info = db.get_lineage(dief_id, db_path=temp_db)
    assert info["replicate_code"] == "R001"
    assert info["sample_code"] == "S001"
    assert info["batch_code"] == "B001"
    assert info["experiment_code"] == "E001"
    assert info["matrix_code"] == "M001"


def test_replicate_requires_existing_sample(temp_db):
    _seed(temp_db)
    with pytest.raises(ValueError):
        db.add_replicate("R001", "S999", "Bad replicate", db_path=temp_db)


def test_migration_adds_replicate_code_to_old_db():
    import sqlite3
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE assays (dief_id TEXT PRIMARY KEY, experiment_code TEXT, "
        "area_code TEXT, matrix_code TEXT, seq INTEGER, created_at TEXT)")
    con.execute("INSERT INTO assays VALUES ('E001_PRO_M001_001','E001','PRO','M001',1,'t')")
    con.commit()
    con.close()
    db.init_db(path)
    rows = db.enriched_assays(path)
    assert rows[0]["replicate_code"] is None
    os.remove(path)


def test_batch_requires_existing_experiment(temp_db):
    with pytest.raises(ValueError):
        db.add_batch("B999", "E_NOPE", "x", db_path=temp_db)


def test_sample_requires_existing_batch_and_matrix(temp_db):
    db.add_experiment("E001", "Pilot", "EXP", db_path=temp_db)
    db.add_batch("B001", "E001", "b", db_path=temp_db)
    with pytest.raises(ValueError):
        db.add_sample("S999", "B001", "M_NOPE", "x", db_path=temp_db)


def test_quality_report_flags_gaps(temp_db):
    _seed(temp_db)  # sample S001 has no assay yet
    rep = db.quality_report(db_path=temp_db)
    assert "S001" in rep["samples_without_assays"]
    db.create_assay_from_sample("S001", "PRO", db_path=temp_db)
    rep2 = db.quality_report(db_path=temp_db)
    assert "S001" not in rep2["samples_without_assays"]
    assert rep2["sample_coverage"] == 1.0


def test_migration_adds_sample_code_to_old_db():
    # Build an OLD-style assays table without sample_code, then migrate.
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE assays (dief_id TEXT PRIMARY KEY, experiment_code TEXT, "
        "area_code TEXT, matrix_code TEXT, seq INTEGER, created_at TEXT)")
    con.execute("INSERT INTO assays VALUES ('E001_PRO_M001_001','E001','PRO','M001',1,'t')")
    con.commit()
    con.close()
    db.init_db(path)  # should add the missing column without losing data
    # enriched_assays must work and keep the old row, now with a null sample_code
    rows = db.enriched_assays(path)
    assert any(r["dief_id"] == "E001_PRO_M001_001" for r in rows)
    assert rows[0]["sample_code"] is None


def test_update_fields_preserves_created_at(temp_db):
    _seed(temp_db)
    before = db.get_row("batches", "B001", db_path=temp_db)["created_at"]
    db.update_fields("batches", "B001", {"name": "Renamed batch"}, db_path=temp_db)
    after = db.get_row("batches", "B001", db_path=temp_db)
    assert after["name"] == "Renamed batch"
    assert after["created_at"] == before  # editing a name must not reset the timestamp


def test_update_fields_experiment_activity(temp_db):
    db.add_experiment("E001", "Pilot", "EXP", db_path=temp_db)
    db.update_fields("experiments", "E001",
                     {"name": "Pilot 2", "activity_code": "LIT"}, db_path=temp_db)
    r = db.get_row("experiments", "E001", db_path=temp_db)
    assert r["name"] == "Pilot 2" and r["activity_code"] == "LIT"


def test_update_fields_ignores_non_editable(temp_db):
    _seed(temp_db)
    # attempting to change the code via update_fields must be ignored
    db.update_fields("areas", "PRO", {"code": "HACK", "name": "Proteomics 2"}, db_path=temp_db)
    assert db.code_exists("areas", "PRO", db_path=temp_db)
    assert not db.code_exists("areas", "HACK", db_path=temp_db)


def test_seed_demo_populates_and_is_idempotent(temp_db):
    db.seed_demo(db_path=temp_db)
    c = db.counts(db_path=temp_db)
    assert c == {"areas": 2, "matrices": 2, "experiments": 2,
                 "batches": 2, "samples": 3, "replicates": 3, "assays": 6}
    # running again must reset to the same state (not accumulate)
    db.seed_demo(db_path=temp_db)
    assert db.counts(db_path=temp_db) == c
    # one direct (sample-less) assay should be present for the quality demo
    rep = db.quality_report(db_path=temp_db)
    assert len(rep["direct_assays"]) == 1
    assert rep["sample_coverage"] == 1.0


def test_clear_all_empties_everything(temp_db):
    db.seed_demo(db_path=temp_db)
    db.clear_all(db_path=temp_db)
    assert db.counts(db_path=temp_db) == {"areas": 0, "matrices": 0, "experiments": 0,
                                          "batches": 0, "samples": 0, "replicates": 0,
                                          "assays": 0}