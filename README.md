# 🧬 DIEF-MO
**A Standardized Data Integration and Encoding Framework for Multi-Omics Data with Lineage Tracking**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
[![tests](https://github.com/deisefs04/DIEF-MO/actions/workflows/tests.yml/badge.svg)](https://github.com/deisefs04/DIEF-MO/actions/workflows/tests.yml)
![License](https://img.shields.io/badge/License-MIT-0090D4)
[![Live demo](https://img.shields.io/badge/Live%20demo-online-0C2D5A)](https://dief-mo-demo.streamlit.app)

**DIEF-MO** (Data Integration and Encoding Framework for Multi-Omics) is a
framework for **standardizing, encoding, and tracing** multi-omics data,
preparing it for integration and use in machine learning. It assigns every assay
a unique, structured identifier and preserves full provenance, from the
experiment down to the individual sample.

🔗 **Live demo:** https://dief-mo-demo.streamlit.app

## 🔬 Overview
Multi-omics data integration is essential for analyzing complex biological
systems and for Artificial Intelligence (AI) applications. Yet heterogeneity,
lack of standardization, and missing traceability routinely compromise the
quality and reproducibility of analyses. DIEF-MO addresses this through a
structured approach to standardization, encoding, and data lineage, so that
data is consistent, traceable, and ready for downstream models.

## ✨ Key features
- Standardized, unique identifiers for every assay
- Controlled vocabularies and code validation, so identifiers stay consistent
- Full data lineage: experiment → batch → sample → identifier, traceable per ID
- Integration of experimental and literature data
- Data-quality checks (completeness, orphan references) and a documented data dictionary
- AI-ready export: one row per identifier with full metadata and lineage (CSV/Excel)
- ISA-Tab-aligned study/assay tables and a FAIR-style metadata record
- Automated information extraction via regex (`decode_id`)
- Scalable and adaptable to different biological domains

## 🎯 Applications
- Multi-omics data integration
- Bioinformatics
- Machine learning applied to biology
- Data governance in data science
- Structuring of experimental data for reproducible pipelines

## 🏷️ Identifier format
Each assay receives a unique standardized identifier composed of subcodes:

```
<EXPERIMENT>_<AREA>_<MATRIX>_<SEQ>
```

Example: `E001_PRO_M001_001`

| Part   | Meaning                                  |
|--------|------------------------------------------|
| `E001` | Experiment code                          |
| `PRO`  | Responsible area                         |
| `M001` | Matrix / sample code                     |
| `001`  | Sequential identifier (auto-incremented) |

The sequence is generated automatically per `experiment + area + matrix`
combination, ensuring stable and traceable identifiers.

### Core entities

- **area_code**: area responsible for the assay
- **activity_code**: data origin, `E` (experimental) or `L` (literature)
- **matrix_code**: analyzed matrix identifier
- **matrix_type**: matrix type
- **experiment_code**: experiment identifier

### Secondary entities (lineage)

Derived from the core entities to capture provenance:

- **batch**: a batch of work belonging to an experiment
- **sample**: a sample belonging to a batch and referencing a matrix
- **replicate**: a replicate belonging to a sample
- **sequence**: the internal sequential index (the `SEQ` part of the
  identifier), auto-incremented per `experiment + area + matrix`

An identifier can be generated directly, from a registered sample, or from a
registered replicate, in which case the rest of the chain is derived from its
lineage (`replicate → sample → batch → experiment`, `sample → matrix`).

## 🚀 Getting started
Requirements: Python 3.10+

```bash
git clone https://github.com/deisefs04/DIEF-MO.git
cd DIEF-MO
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py             # opens at http://localhost:8501
python -m pytest                 # run the test suite
```

## ⚙️ Usage
The application provides eight pages:

1. **Overview**: summary counts and demo data controls.
2. **Registration**: register core data (areas, matrices, experiments) and
   lineage entities (batches, samples), with controlled vocabularies and
   validated codes.
3. **Generate ID**: generate an identifier from a registered sample (with
   derived lineage) or directly from experiment + area + matrix.
4. **Batch import**: upload an Excel file (`.xlsx`) with the columns
   `experiment_code`, `area_code`, `matrix_code` to generate identifiers in bulk.
5. **Lineage**: trace any identifier back through sample, batch and experiment,
   and browse the full experiment tree.
6. **Data quality**: completeness checks, orphan-reference detection and the
   data dictionary for the exported dataset.
7. **FAIR / ISA-Tab**: ISA-aligned study/assay tables, a FAIR metadata record,
   and a downloadable bundle.
8. **History**: browse all generated identifiers and export the AI-ready dataset.

### Using the library directly

```python
from dief_mo import generate_id, decode_id

generate_id("E001", "PRO", "M001", 1)   # 'E001_PRO_M001_001'
decode_id("E001_PRO_M001_001")          # {'experiment': 'E001', 'area': 'PRO',
                                        #  'matrix': 'M001', 'seq': 1}
```

## 🗂️ Project structure
```
DIEF-MO/
├── app.py                  # Streamlit interface
├── dief_mo/
│   ├── encoder.py          # generate_id / decode_id / validate_code (core)
│   ├── vocab.py            # controlled vocabularies (edit to match your catalog)
│   ├── datadict.py         # data dictionary for the exported dataset
│   ├── isa.py              # ISA-Tab-aligned & FAIR exports
│   └── db.py               # SQLite persistence (entities, lineage, quality)
├── tests/                  # test_encoder.py, test_db.py, test_isa.py
├── .streamlit/config.toml  # theme
├── requirements.txt
└── LICENSE
```

## 🧩 Standards & FAIR
DIEF-MO exports an **ISA-Tab-aligned** representation (investigation, study and
assay files) and a **FAIR-style metadata record** (JSON), available as a single
downloadable bundle from the *FAIR / ISA-Tab* page. The output follows ISA-Tab
conventions but is **not** validated against the ISA specification by a certified
tool; fully validated ISA output via the `isatools` library is on the roadmap.

## 💡 Use case
The framework was applied in a pilot study with real multi-omics data from
microorganism matrices, integrating experimental and literature data into a
structured tabular format ready for ingestion in AI pipelines.

## 🗺️ Roadmap
- Validated ISA-Tab/ISA-JSON output via the `isatools` library, with ontology
  term sources (OBI, NCBITaxon) and MIAME/MIAPE checklists.
- Optional hosted database for shared, persistent multi-user deployments.

## 📚 How to cite
If this work is useful in your research, please cite it:

```bibtex
@inproceedings{souza2026diefmo,
  title     = {DIEF-MO: A Standardized Data Integration and Encoding Framework for Multi-Omics Data with Lineage Tracking},
  author    = {Souza, Deise F. and Kamassury, Jorge and Arantes, Márcio S. and Violada, Paulo A. M. V. and Barbosa, Flávio G. O. and Soratto, Tatiany A. T. and Danzer, Emerson W.},
  booktitle = {Proceedings of the X-Meeting 2026 (AB3C)},
  year      = {2026},
  note      = {ISBN to be assigned}
}
```

## 👥 Authors
Developed by the DIEF-MO team at the Instituto SENAI de Inovação em Sistemas
Embarcados (ISI-SE), Brazil. See *How to cite* above for the full author list.

## 📄 License
Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.