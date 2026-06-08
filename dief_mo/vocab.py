"""Controlled vocabularies for DIEF-MO.

These are sensible DEFAULT lists. Edit them to match your project's official
catalogs. They are kept here (and version-controlled) on purpose, so any
change to the standard is explicit and reviewable in a pull request.
"""

# Activity types: origin of the data (poster: E = experimental, L = literature).
ACTIVITY_TYPES = {
    "E": "Experimental",
    "L": "Literature",
}

# Suggested area codes (omics layers / responsible areas).
# Users may still register custom areas.
SUGGESTED_AREAS = {
    "GEN": "Genomics",
    "TRA": "Transcriptomics",
    "PRO": "Proteomics",
    "MET": "Metabolomics",
    "EPI": "Epigenomics",
    "MIC": "Microbiomics",
    "LIP": "Lipidomics",
}

# Controlled matrix types.
MATRIX_TYPES = [
    "Bacterial culture",
    "Fungal culture",
    "Viral sample",
    "Cell culture",
    "Tissue",
    "Plant material",
    "Environmental sample",
    "Other",
]