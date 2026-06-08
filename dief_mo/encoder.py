"""Core ID encoding/decoding for the DIEF-MO framework.

A DIEF-MO identifier follows the pattern:
    <EXPERIMENT>_<AREA>_<MATRIX>_<SEQ>
for example: E001_PRO_M001_001
"""
import re

DIEF_ID_PATTERN = re.compile(
    r"^(?P<experiment>[A-Za-z0-9]+)_"
    r"(?P<area>[A-Za-z0-9]+)_"
    r"(?P<matrix>[A-Za-z0-9]+)_"
    r"(?P<seq>\d{3,})$"
)

CODE_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


def validate_code(value, label="code"):
    """Validate and normalise a single code part. Returns the trimmed value."""
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"'{label}' nao pode ser vazio.")
    if not CODE_PATTERN.match(text):
        raise ValueError(
            f"'{label}' invalido: use apenas letras e numeros, sem espacos, "
            f"'_' ou simbolos (recebido: {value!r})."
        )
    return text


def generate_id(experiment, area, matrix, seq):
    """Build a DIEF-MO identifier from its parts."""
    experiment = validate_code(experiment, "experiment")
    area = validate_code(area, "area")
    matrix = validate_code(matrix, "matrix")
    seq = int(seq)
    if seq < 1:
        raise ValueError("'seq' deve ser >= 1.")
    return f"{experiment}_{area}_{matrix}_{seq:03d}"


def decode_id(dief_id):
    """Parse a DIEF-MO identifier back into its components using regex."""
    match = DIEF_ID_PATTERN.match(str(dief_id).strip())
    if not match:
        raise ValueError(f"Identificador invalido: {dief_id!r}")
    parts = match.groupdict()
    parts["seq"] = int(parts["seq"])
    return parts
