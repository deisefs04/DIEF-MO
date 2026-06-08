"""DIEF-MO Encoder - Streamlit interface.

Run with:  streamlit run app.py
"""
import io

import pandas as pd
import streamlit as st

from dief_mo import db, isa, vocab
from dief_mo.datadict import DATA_DICTIONARY
from dief_mo.encoder import decode_id, validate_code

st.set_page_config(page_title="DIEF-MO", page_icon="🧬", layout="wide")
db.init_db()

# --- light visual polish (self-contained, version-robust) ---------------
st.markdown(
    """
    <style>
      /* hide default Streamlit chrome for an app-like demo */
      #MainMenu, footer {visibility: hidden;}
      [data-testid="stHeader"] {background: transparent; height: 0;}
      .block-container {padding-top: 2.2rem; max-width: 1200px;}
      /* branded sidebar title */
      .dief-sidebar-title {color: #FFFFFF; font-family: Archivo, sans-serif;
          font-weight: 700; font-size: 1.35rem; letter-spacing: .02em; margin: .2rem 0 0;}
      .dief-sidebar-sub {color: #9FC3E8; font-size: .72rem; text-transform: uppercase;
          letter-spacing: .14em; margin: 0 0 .4rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def page_header(title, subtitle=""):
    """Consistent branded header for every page."""
    sub = (f'<p style="margin:.3rem 0 0;color:#5A6B82;font-size:.95rem;">{subtitle}</p>'
           if subtitle else "")
    st.markdown(
        f"""
        <div style="margin:0 0 1.3rem 0;">
          <div style="height:4px;width:52px;background:#0090D4;border-radius:2px;margin-bottom:.7rem;"></div>
          <h1 style="margin:0;font-family:Archivo,sans-serif;color:#0C2D5A;
              font-size:1.95rem;font-weight:700;line-height:1.1;">{title}</h1>
          {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


st.sidebar.markdown(
    '<div class="dief-sidebar-title">🧬 DIEF-MO</div>'
    '<div class="dief-sidebar-sub">Multi-omics encoding</div>',
    unsafe_allow_html=True,
)
page = st.sidebar.radio(
    "Navigation",
    ["Overview", "Registration", "Generate ID", "Batch import",
     "Lineage", "Data quality", "FAIR / ISA-Tab", "History"],
)


_EDIT_FIELDS = {
    "areas": [("name", "Name", "text"), ("description", "Description", "text")],
    "matrices": [("name", "Name", "text"), ("matrix_type", "Matrix type", "matrixtype")],
    "experiments": [("name", "Name", "text"), ("activity_code", "Activity", "activity")],
    "batches": [("name", "Name", "text")],
    "samples": [("name", "Name", "text")],
    "replicates": [("name", "Name", "text")],
}


def _manage_control(table, label):
    """Expander to edit (descriptive fields) or delete a registered entry."""
    rows = db.list_table(table)
    if not rows:
        return
    with st.expander(f"Manage {label}s (edit / delete)"):
        target = st.selectbox(f"Select a {label}", [r["code"] for r in rows], key=f"mng_{table}")
        record = next(r for r in rows if r["code"] == target)
        new_vals = {}
        for field, flabel, kind in _EDIT_FIELDS[table]:
            cur = record.get(field) or ""
            if kind == "matrixtype":
                opts = vocab.MATRIX_TYPES
                idx = opts.index(cur) if cur in opts else len(opts) - 1
                sel = st.selectbox(flabel, opts, index=idx, key=f"edt_{table}_{field}")
                if sel == "Other":
                    sel = st.text_input("Specify matrix type", value=cur, key=f"edt_{table}_{field}_o")
                new_vals[field] = sel
            elif kind == "activity":
                acts = list(vocab.ACTIVITY_TYPES.keys())
                idx = acts.index(cur) if cur in acts else 0
                labels = [f"{c} · {n}" for c, n in vocab.ACTIVITY_TYPES.items()]
                sel = st.selectbox(flabel, labels, index=idx, key=f"edt_{table}_{field}")
                new_vals[field] = sel.split(" · ")[0]
            else:
                new_vals[field] = st.text_input(flabel, value=cur, key=f"edt_{table}_{field}")
        c1, c2 = st.columns(2)
        if c1.button("Update", key=f"upd_{table}"):
            db.update_fields(table, target, new_vals)
            st.success(f"{label} '{target}' updated.")
            st.rerun()
        if c2.button(f"Delete '{target}'", key=f"delbtn_{table}"):
            db.delete_row(table, target)
            st.rerun()


def _save_with_feedback(table, code, label, save_fn):
    """Run a save function with validation feedback. save_fn() does the insert."""
    try:
        existed = db.code_exists(table, code)
        save_fn()
        st.success(f"{label} '{code}' {'updated' if existed else 'saved'}.")
    except ValueError as e:
        st.error(str(e))


# ------------------------------------------------------------------- Overview
if page == "Overview":
    page_header("Overview")
    st.write(
        "Standardize, encode and trace multi-omics assays. Register core data "
        "(areas, matrices, experiments) and optional lineage (batches, samples, "
        "replicates), then generate stable identifiers `EXPERIMENT_AREA_MATRIX_SEQ`."
    )
    c = db.counts()
    cards = [("Areas", c["areas"]), ("Matrices", c["matrices"]),
             ("Experiments", c["experiments"]), ("Batches", c["batches"]),
             ("Samples", c["samples"]), ("Replicates", c["replicates"]),
             ("Generated IDs", c["assays"])]
    cols = st.columns(3)
    for i, (label, value) in enumerate(cards):
        with cols[i % 3].container(border=True):
            st.metric(label, value)
    if c["areas"] == 0 or c["matrices"] == 0 or c["experiments"] == 0:
        st.info("Start in **Registration** to add at least one area, matrix and experiment.")

    st.divider()
    st.caption("Demo controls")
    colA, colB = st.columns(2)
    if colA.button("Load example data"):
        db.seed_demo()
        st.rerun()
    if colB.button("Clear all data"):
        db.clear_all()
        st.rerun()

# --------------------------------------------------------------- Registration
elif page == "Registration":
    page_header("Registration")
    st.caption("Core entities define the identifier. Batches and samples add lineage.")
    tabs = st.tabs(["Areas", "Matrices", "Experiments", "Batches", "Samples", "Replicates"])

    # ----- Areas -----
    with tabs[0]:
        options = [f"{c} · {n}" for c, n in vocab.SUGGESTED_AREAS.items()]
        choice = st.selectbox("Area", options + ["Custom..."], key="area_choice")
        if choice == "Custom...":
            code = st.text_input("Area code (letters/numbers only, e.g. PRO)", key="area_code")
            name = st.text_input("Name", key="area_name")
        else:
            code, name = choice.split(" · ", 1)
            st.text_input("Area code", value=code, disabled=True)
            st.text_input("Name", value=name, disabled=True)
        desc = st.text_input("Description (optional)", key="area_desc")
        if st.button("Save area"):
            try:
                code = validate_code(code, "area code")
                if not name.strip():
                    raise ValueError("Name is required.")
                _save_with_feedback("areas", code, "Area", lambda: db.add_area(code, name, desc))
            except ValueError as e:
                st.error(str(e))
        st.dataframe(pd.DataFrame(db.list_table("areas")), use_container_width=True)
        _manage_control("areas", "area")

    # ----- Matrices -----
    with tabs[1]:
        code = st.text_input("Matrix code (letters/numbers only, e.g. M001)", key="mx_code")
        name = st.text_input("Name", key="mx_name")
        mtype = st.selectbox("Matrix type", vocab.MATRIX_TYPES, key="mx_type")
        if mtype == "Other":
            mtype = st.text_input("Specify matrix type", key="mx_type_other")
        if st.button("Save matrix"):
            try:
                code = validate_code(code, "matrix code")
                if not name.strip():
                    raise ValueError("Name is required.")
                _save_with_feedback("matrices", code, "Matrix",
                                    lambda: db.add_matrix(code, name, mtype))
            except ValueError as e:
                st.error(str(e))
        st.dataframe(pd.DataFrame(db.list_table("matrices")), use_container_width=True)
        _manage_control("matrices", "matrix")

    # ----- Experiments -----
    with tabs[2]:
        code = st.text_input("Experiment code (letters/numbers only, e.g. E001)", key="ex_code")
        name = st.text_input("Name", key="ex_name")
        activity_label = st.selectbox(
            "Activity type", [f"{c} · {n}" for c, n in vocab.ACTIVITY_TYPES.items()],
            key="ex_activity")
        activity = activity_label.split(" · ")[0]
        if st.button("Save experiment"):
            try:
                code = validate_code(code, "experiment code")
                if not name.strip():
                    raise ValueError("Name is required.")
                _save_with_feedback("experiments", code, "Experiment",
                                    lambda: db.add_experiment(code, name, activity))
            except ValueError as e:
                st.error(str(e))
        st.dataframe(pd.DataFrame(db.list_table("experiments")), use_container_width=True)
        _manage_control("experiments", "experiment")

    # ----- Batches -----
    with tabs[3]:
        experiments = db.list_table("experiments")
        if not experiments:
            st.warning("Register an experiment first.")
        else:
            code = st.text_input("Batch code (letters/numbers only, e.g. B001)", key="bt_code")
            name = st.text_input("Name", key="bt_name")
            exp = st.selectbox("Experiment", [e["code"] for e in experiments], key="bt_exp")
            if st.button("Save batch"):
                try:
                    code = validate_code(code, "batch code")
                    if not name.strip():
                        raise ValueError("Name is required.")
                    _save_with_feedback("batches", code, "Batch",
                                        lambda: db.add_batch(code, exp, name))
                except ValueError as e:
                    st.error(str(e))
        st.dataframe(pd.DataFrame(db.list_table("batches")), use_container_width=True)
        _manage_control("batches", "batch")

    # ----- Samples -----
    with tabs[4]:
        batches = db.list_table("batches")
        matrices = db.list_table("matrices")
        if not (batches and matrices):
            st.warning("Register a batch and a matrix first.")
        else:
            code = st.text_input("Sample code (letters/numbers only, e.g. S001)", key="sp_code")
            name = st.text_input("Name", key="sp_name")
            batch = st.selectbox("Batch", [b["code"] for b in batches], key="sp_batch")
            matrix = st.selectbox("Matrix", [m["code"] for m in matrices], key="sp_matrix")
            if st.button("Save sample"):
                try:
                    code = validate_code(code, "sample code")
                    if not name.strip():
                        raise ValueError("Name is required.")
                    _save_with_feedback("samples", code, "Sample",
                                        lambda: db.add_sample(code, batch, matrix, name))
                except ValueError as e:
                    st.error(str(e))
        st.dataframe(pd.DataFrame(db.list_table("samples")), use_container_width=True)
        _manage_control("samples", "sample")

    # ----- Replicates -----
    with tabs[5]:
        samples = db.list_table("samples")
        if not samples:
            st.warning("Register a sample first.")
        else:
            code = st.text_input("Replicate code (letters/numbers only, e.g. R001)", key="rp_code")
            name = st.text_input("Name", key="rp_name")
            sample = st.selectbox("Sample", [s["code"] for s in samples], key="rp_sample")
            if st.button("Save replicate"):
                try:
                    code = validate_code(code, "replicate code")
                    if not name.strip():
                        raise ValueError("Name is required.")
                    _save_with_feedback("replicates", code, "Replicate",
                                        lambda: db.add_replicate(code, sample, name))
                except ValueError as e:
                    st.error(str(e))
        st.dataframe(pd.DataFrame(db.list_table("replicates")), use_container_width=True)
        _manage_control("replicates", "replicate")

# ------------------------------------------------------------------ Generate ID
elif page == "Generate ID":
    page_header("Generate a DIEF-MO identifier")
    mode = st.radio("Mode", ["From a registered replicate", "From a registered sample",
                             "Direct (experiment + area + matrix)"])

    areas = db.list_table("areas")

    if mode == "From a registered replicate":
        replicates = db.list_table("replicates")
        if not (replicates and areas):
            st.warning("Register at least one replicate and one area first.")
        else:
            replicate = st.selectbox("Replicate", [r["code"] for r in replicates])
            area = st.selectbox("Area", [a["code"] for a in areas])
            rp = db.get_row("replicates", replicate)
            s = db.get_row("samples", rp["sample_code"]) if rp else None
            b = db.get_row("batches", s["batch_code"]) if s else None
            if b and s:
                st.caption(f"Derived lineage → experiment **{b['experiment_code']}**, "
                           f"matrix **{s['matrix_code']}**, batch **{s['batch_code']}**, "
                           f"sample **{s['code']}**")
            if st.button("Generate ID"):
                dief_id = db.create_assay_from_replicate(replicate, area)
                st.success(f"Generated ID: {dief_id}")
                st.json(decode_id(dief_id))

    elif mode == "From a registered sample":
        samples = db.list_table("samples")
        if not (samples and areas):
            st.warning("Register at least one sample and one area first.")
        else:
            sample = st.selectbox("Sample", [s["code"] for s in samples])
            area = st.selectbox("Area", [a["code"] for a in areas])
            s = db.get_row("samples", sample)
            b = db.get_row("batches", s["batch_code"]) if s else None
            if b:
                st.caption(f"Derived lineage → experiment **{b['experiment_code']}**, "
                           f"matrix **{s['matrix_code']}**, batch **{s['batch_code']}**")
            if st.button("Generate ID"):
                dief_id = db.create_assay_from_sample(sample, area)
                st.success(f"Generated ID: {dief_id}")
                st.json(decode_id(dief_id))
    else:
        experiments = db.list_table("experiments")
        matrices = db.list_table("matrices")
        if not (experiments and areas and matrices):
            st.warning("Register at least one experiment, one area and one matrix first.")
        else:
            col1, col2, col3 = st.columns(3)
            exp = col1.selectbox("Experiment", [e["code"] for e in experiments])
            area = col2.selectbox("Area", [a["code"] for a in areas])
            matrix = col3.selectbox("Matrix", [m["code"] for m in matrices])
            if st.button("Generate ID"):
                dief_id = db.create_assay(exp, area, matrix)
                st.success(f"Generated ID: {dief_id}")
                st.json(decode_id(dief_id))

# --------------------------------------------------------------- Batch import
elif page == "Batch import":
    page_header("Batch import (Excel)")
    st.caption("The file must contain the columns: experiment_code, area_code, matrix_code")
    file = st.file_uploader("Upload an Excel file (.xlsx)", type=["xlsx"])
    if file:
        df = pd.read_excel(file)
        st.dataframe(df, use_container_width=True)
        required = ["experiment_code", "area_code", "matrix_code"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error(f"Missing columns: {', '.join(missing)}")
        elif st.button("Generate IDs"):
            results, errors = [], []
            for idx, r in df.iterrows():
                try:
                    results.append(db.create_assay(
                        r["experiment_code"], r["area_code"], r["matrix_code"]))
                except ValueError as e:
                    results.append(None)
                    errors.append(f"Row {idx + 1}: {e}")
            df["dief_id"] = results
            st.dataframe(df, use_container_width=True)
            if errors:
                st.warning("Some rows could not be processed:\n\n" + "\n".join(errors))
            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            st.download_button("Download result", buf.getvalue(), file_name="dief_output.xlsx")

# ----------------------------------------------------------------- Lineage
elif page == "Lineage":
    page_header("Data lineage")
    assays = db.list_table("assays")
    if not assays:
        st.info("No identifiers generated yet.")
    else:
        chosen = st.selectbox("Select an identifier", [a["dief_id"] for a in assays])
        info = db.get_lineage(chosen)
        if info:
            chain = f"**{info['dief_id']}**"
            if info.get("replicate_code"):
                chain += f"  ←  replicate **{info['replicate_code']}**"
            if info.get("sample_code"):
                chain += (f"  ←  sample **{info['sample_code']}**"
                          f"  ←  batch **{info.get('batch_code')}**"
                          f"  ←  experiment **{info['experiment_code']}**")
            else:
                chain += f"  ←  experiment **{info['experiment_code']}** (direct, no sample)"
            st.markdown(chain)
            st.markdown(f"matrix **{info['matrix_code']}** ({info.get('matrix_type') or '-'})  |  "
                        f"area **{info['area_code']}**  |  activity **{info.get('activity_code') or '-'}**")
            st.json(info)
    st.subheader("Experiment tree")
    tree = db.experiment_tree()
    if not any(node["batches"] for node in tree):
        st.caption("Register batches and samples to populate the lineage tree.")
    for node in tree:
        e = node["experiment"]
        with st.expander(f"{e['code']} · {e['name']}"):
            if not node["batches"]:
                st.caption("No batches.")
            for bn in node["batches"]:
                b = bn["batch"]
                st.markdown(f"**Batch {b['code']}** · {b['name']}")
                for sn in bn["samples"]:
                    s = sn["sample"]
                    ids = ", ".join(a["dief_id"] for a in sn["assays"]) or "no IDs yet"
                    st.markdown(f"- Sample {s['code']} ({s['matrix_code']}): {ids}")
                    reps = ", ".join(r["code"] for r in sn["replicates"])
                    if reps:
                        st.markdown(f"    - replicates: {reps}")

# -------------------------------------------------------------- Data quality
elif page == "Data quality":
    page_header("Data quality & AI-readiness")
    rep = db.quality_report()

    cov = rep["sample_coverage"]
    st.metric("Sample coverage (samples with at least one ID)",
              "-" if cov is None else f"{cov * 100:.0f}%")

    checks = [
        ("Experiments without batches", rep["experiments_without_batches"]),
        ("Batches without samples", rep["batches_without_samples"]),
        ("Samples without identifiers", rep["samples_without_assays"]),
        ("Replicates without identifiers", rep["replicates_without_assays"]),
        ("Orphan batches (missing experiment)", rep["orphan_batches"]),
        ("Orphan samples (missing batch/matrix)", rep["orphan_samples"]),
        ("Orphan replicates (missing sample)", rep["orphan_replicates"]),
        ("Identifiers generated without a sample link", rep["direct_assays"]),
    ]
    for label, items in checks:
        if items:
            st.warning(f"{label}: {', '.join(items)}")
        else:
            st.success(f"{label}: none")

    st.subheader("Data dictionary (exported dataset)")
    st.dataframe(
        pd.DataFrame(DATA_DICTIONARY, columns=["column", "description", "type"]),
        use_container_width=True)

# ------------------------------------------------------------- FAIR / ISA-Tab
elif page == "FAIR / ISA-Tab":
    page_header("FAIR / ISA-Tab export")
    st.caption(
        "ISA-Tab-aligned tables and a FAIR-style metadata record. This follows "
        "ISA conventions but is not validated by a certified ISA tool; see the "
        "roadmap for fully validated output via isatools."
    )

    st.subheader("Investigation metadata")
    col1, col2 = st.columns(2)
    meta = {
        "identifier": col1.text_input("Identifier", "DIEF-MO"),
        "title": col1.text_input("Title", "DIEF-MO multi-omics dataset"),
        "contact_name": col2.text_input("Contact name", ""),
        "contact_email": col2.text_input("Contact email", ""),
        "keywords": st.text_input("Keywords (comma-separated)", "multi-omics, metadata, data lineage"),
        "description": st.text_area("Description", ""),
        "license": st.text_input("License", "MIT"),
    }

    st.subheader("ISA study table (one row per sample)")
    study = isa.study_table()
    st.dataframe(study, use_container_width=True)

    st.subheader("ISA assay table (one row per sample-linked identifier)")
    assay = isa.assay_table()
    if assay.empty:
        st.info("No sample-linked identifiers yet. Generate IDs from registered "
                "samples to populate the ISA assay table.")
    else:
        st.dataframe(assay, use_container_width=True)

    st.subheader("FAIR alignment")
    st.table(pd.DataFrame(isa.FAIR_ALIGNMENT, columns=["Principle", "How DIEF-MO addresses it"]))

    st.subheader("Download")
    st.download_button(
        "Download FAIR / ISA-Tab bundle (.zip)",
        isa.build_bundle(meta),
        file_name="dief_fair_isa_bundle.zip",
        mime="application/zip",
    )
    st.caption("Bundle: i_investigation.txt, s_study.txt, a_assay.txt, "
               "dief_dataset.csv, fair_metadata.json, data_dictionary.csv")

# -------------------------------------------------------------------- History
elif page == "History":
    page_header("Generated IDs")
    rows = db.enriched_assays()
    if not rows:
        st.info("No IDs generated yet.")
    else:
        df = pd.DataFrame(rows)
        fcol1, fcol2 = st.columns([2, 1])
        search = fcol1.text_input("Filter (search across all columns)", "")
        activities = ["All"] + sorted({r.get("activity_code") for r in rows if r.get("activity_code")})
        act = fcol2.selectbox("Activity", activities)

        view = df
        if act != "All":
            view = view[view["activity_code"] == act]
        if search:
            mask = view.apply(
                lambda r: r.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
            view = view[mask]

        st.dataframe(view, use_container_width=True)
        by_activity = df["activity_code"].fillna("(none)").value_counts().to_dict()
        breakdown = ", ".join(f"{k}: {v}" for k, v in by_activity.items())
        st.caption(f"Showing {len(view)} of {len(df)} identifiers  |  by activity → {breakdown}")
        st.caption("AI-ready export: one row per identifier with full metadata and lineage.")
        col1, col2 = st.columns(2)
        col1.download_button("Download CSV", view.to_csv(index=False).encode("utf-8"),
                             file_name="dief_dataset.csv", mime="text/csv")
        buf = io.BytesIO()
        view.to_excel(buf, index=False)
        col2.download_button("Download Excel", buf.getvalue(), file_name="dief_dataset.xlsx")