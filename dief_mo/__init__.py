"""DIEF-MO: AI-Ready Multi-Omics Data Integration & Encoding Framework."""
from .encoder import generate_id, decode_id, DIEF_ID_PATTERN

__all__ = ["generate_id", "decode_id", "DIEF_ID_PATTERN"]
__version__ = "0.1.0"
