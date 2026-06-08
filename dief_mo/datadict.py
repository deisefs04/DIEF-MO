"""Data dictionary for the AI-ready exported dataset.

Documents every column produced by ``db.enriched_assays`` so the published
dataset is self-describing (a step toward FAIR-aligned outputs).
"""

DATA_DICTIONARY = [
    ("dief_id", "Unique DIEF-MO identifier (EXPERIMENT_AREA_MATRIX_SEQ).", "string"),
    ("experiment_code", "Code of the experiment.", "string"),
    ("experiment_name", "Human-readable experiment name.", "string"),
    ("activity_code", "Data origin: E (experimental) or L (literature).", "categorical"),
    ("area_code", "Code of the responsible area.", "string"),
    ("area_name", "Human-readable area name.", "string"),
    ("matrix_code", "Code of the analyzed matrix.", "string"),
    ("matrix_name", "Human-readable matrix name.", "string"),
    ("matrix_type", "Controlled matrix type.", "categorical"),
    ("sample_code", "Linked sample code (empty for directly generated IDs).", "string"),
    ("sample_name", "Human-readable sample name.", "string"),
    ("replicate_code", "Linked replicate code (empty when no replicate).", "string"),
    ("replicate_name", "Human-readable replicate name.", "string"),
    ("batch_code", "Batch the sample belongs to.", "string"),
    ("batch_name", "Human-readable batch name.", "string"),
    ("seq", "Sequential index (the SEQ / Sequence) within experiment+area+matrix.", "integer"),
    ("created_at", "UTC timestamp when the identifier was generated.", "datetime"),
]