import io
import json
import os
import tempfile
import zipfile

import pytest

from dief_mo import db, isa


@pytest.fixture
def seeded_db():
    path = os.path.join(tempfile.mkdtemp(), "isa.db")
    db.init_db(path)
    db.add_area("PRO", "Proteomics", db_path=path)
    db.add_matrix("M001", "E. coli", "Bacterial culture", db_path=path)
    db.add_experiment("E001", "Pilot", "EXP", db_path=path)
    db.add_batch("B001", "E001", "First batch", db_path=path)
    db.add_sample("S001", "B001", "M001", "Sample 1", db_path=path)
    db.create_assay_from_sample("S001", "PRO", db_path=path)  # sample-linked
    db.create_assay("E001", "PRO", "M001", db_path=path)      # direct, no sample
    return path


def test_study_table_has_isa_columns(seeded_db):
    df = isa.study_table(seeded_db)
    assert "Source Name" in df.columns
    assert "Sample Name" in df.columns
    assert df.iloc[0]["Sample Name"] == "S001"


def test_assay_table_excludes_direct_ids(seeded_db):
    df = isa.assay_table(seeded_db)
    # only the sample-linked id should appear
    assert list(df["Assay Name"]) == ["E001_PRO_M001_001"]


def test_fair_record_fields(seeded_db):
    rec = isa.fair_record({"title": "T", "contact_name": "Jorge"}, db_path=seeded_db)
    assert rec["title"] == "T"
    assert rec["creators"] == ["Jorge"]
    assert rec["record_counts"]["samples"] == 1
    assert any(c["column"] == "dief_id" for c in rec["data_dictionary"])


def test_bundle_is_valid_zip(seeded_db):
    data = isa.build_bundle({"title": "T"}, db_path=seeded_db)
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    assert {"i_investigation.txt", "s_study.txt", "a_assay.txt",
            "dief_dataset.csv", "fair_metadata.json", "data_dictionary.csv"} <= names
    # the FAIR record must be valid JSON
    json.loads(z.read("fair_metadata.json"))