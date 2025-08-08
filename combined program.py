import streamlit as st
import pandas as pd
import io
import os
import re
from io import BytesIO
from zipfile import ZipFile

st.title("Cognitive Task Data Analyzer")

task_choice = st.selectbox(
    "Choose a program:",
    ["Visual Search Task Data Analysis", "Stroop Task Data Analysis"]
)

# -------------------------------
# Common helpers
# -------------------------------
def map_time(raw):
    raw = str(raw).upper()
    if raw == "POST1":
        return "POST15"
    if raw == "POST2":
        return "POST30"
    return raw

def read_any(file, skiprows=3):
    """Read an UploadedFile (CSV/XLSX)."""
    ext = os.path.splitext(file.name)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file, skiprows=skiprows)
    elif ext == ".xlsx":
        return pd.read_excel(file, skiprows=skiprows, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def read_any_from_bytes(name: str, data: bytes, skiprows=3):
    """Read CSV/XLSX from bytes (for ZIP members or unified handling)."""
    ext = os.path.splitext(name)[1].lower()
    bio = BytesIO(data)
    if ext == ".csv":
        return pd.read_csv(bio, skiprows=skiprows)
    elif ext == ".xlsx":
        return pd.read_excel(bio, skiprows=skiprows, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file type: {ext}")

# ===============================
# Visual Search (multi-file or ZIP)
# ===============================
if task_choice == "Visual Search Task Data Analysis":
    st.header("Visual Search Task")

    col1, col2 = st.columns(2)
    with col1:
        uploaded_files = st.file_uploader(
            "Upload ALL Visual Search files (CSV/XLSX) at once",
            type=["csv", "xlsx"],
            accept_multiple_files=True
        )
    with col2:
        zip_file = st.file_uploader("…or upload a ZIP containing folders/files", type=["zip"])

    def parse_vs_filename(name: str):
        """
        Expect: P#_VisualSearch_CONDITION_TIMEPOINT.ext
        Works even if nested path like sub/dir/P8_VisualSearch_CRL_PRE.csv
        """
        base = os.path.splitext(os.path.basename(name))[0]
        parts = base.split("_")
        if len(parts) < 4:
            return None
        participant = parts[0].replace("P", "").strip()
        condition = parts[2].upper().strip()
        time_label = map_time(parts[3])
        return participant, condition, time_label

    def clean_vs_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        # D, E, F, S, T => 3, 4, 5, 18, 19
        needed_idx = [3, 4, 5, 18, 19]
        if max(needed_idx) >= df.shape[1]:
            return pd.DataFrame()
        sub = df.iloc[:, needed_idx].copy()
        sub.columns = ["TargetPresence", "SearchType", "SetSizeRaw", "ResponseTime", "Correct"]
        return sub

    all_rows = []

    # A) loose files
    if uploaded_files:
        for uf in uploaded_files:
            meta = parse_vs_filename(uf.name)
            if not meta:
                st.warning(f"Skipping unrecognized file name: {uf.name}")
                continue
            participant, condition, time_label = meta
            try:
                df = read_any(uf, skiprows=3)
                sub = clean_vs_dataframe(df)
                if sub.empty:
                    st.warning(f"{uf.name}: not enough columns; skipped.")
                    continue
                sub.insert(0, "Participant", participant)
                sub.insert(1, "Condition", condition)
                sub.insert(2, "Time", time_label)
                all_rows.append(sub)
            except Exception as e:
                st.error(f"{uf.name}: {e}")

    # B) ZIP (nested OK)
    if zip_file is not None:
        try:
            with ZipFile(zip_file) as zf:
                for member in zf.namelist():
                    if member.endswith("/"):
                        continue
                    ext = os.path.splitext(member)[1].lower()
                    if ext not in (".csv", ".xlsx"):
                        continue
                    meta = parse_vs_filename(member)
                    if not meta:
                        st.warning(f"Skipping unrecognized file name in ZIP: {member}")
                        continue
                    participant, condition, time_label = meta

                    with zf.open(member) as f:
                        data = f.read()
                    df = read_any_from_bytes(member, data, skiprows=3)

                    sub = clean_vs_dataframe(df)
                    if sub.empty:
                        st.warning(f"{member}: not enough columns; skipped.")
                        continue
                    sub.insert(0, "Participant", participant)
                    sub.insert(1, "Condition", condition)
                    sub.insert(2, "Time", time_label)
                    all_rows.append(sub)
        except Exception as e:
            st.error(f"ZIP error: {e}")

    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True)

        # pieces
        combined["SetSize"] = combined["SetSizeRaw"].astype(str).str[:2]
        combined["ConditionLabel"] = (
            combined["SearchType"].astype(str).str.strip().str.lower().map({
                "feature": "Feature",
                "conjunction": "Conj"
            })
        )
        combined["PresenceLabel"] = (
            combined["TargetPresence"].astype(str).str.strip().str.lower().map({
                "present": "P",
                "absent": "A"
            })
        )

        combined["Correct"] = pd.to_numeric(combined["Correct"], errors="coerce")
        combined["ResponseTime"] = pd.to_numeric(combined["ResponseTime"], errors="coerce")
        combined = combined.dropna(subset=["ConditionLabel", "PresenceLabel", "SetSize"])

        # Group label (FULL)
        combined["Group"] = (
            "P" + combined["Participant"].astype(str) + "_" +
            combined["Condition"].astype(str) + "_" +
            combined["Time"].astype(str) + "_" +
            combined["ConditionLabel"] + "_" +
            combined["PresenceLabel"] + "_" +
            combined["SetSize"]
        )

        # stats
        group_totals = combined.groupby("Group")["Correct"].size()
        correct_mask = combined["Correct"] == 1
        correct_counts = combined[correct_mask].groupby("Group")["Correct"].size()
        mean_rt = combined[correct_mask].groupby("Group")["ResponseTime"].mean()
        sd_rt = combined[correct_mask].groupby("Group")["ResponseTime"].std()

        stats_df = pd.DataFrame({
            "Accurate Responses": correct_counts,
            "Mean RT": mean_rt,
            "SD RT": sd_rt
        })
        stats_df = stats_df.reindex(group_totals.index, fill_value=0)
        stats_df["Percent Accuracy"] = (stats_df["Accurate Responses"] / group_totals * 100).round(2)
        stats_df["Mean RT"] = stats_df["Mean RT"].round(2)
        stats_df["SD RT"] = stats_df["SD RT"].round(2)

        # Summary with meta columns
        meta_df = (
            combined.groupby("Group")
            .agg(
                Participant=("Participant", "first"),
                Condition=("Condition", "first"),
                Time=("Time", "first"),
                ConditionType=("ConditionLabel", "first"),
                TargetPresence=("PresenceLabel", "first"),
                SetSize=("SetSize", "first")
            )
        )
        summary_df = meta_df.join(
            stats_df[["Accurate Responses", "Mean RT", "SD RT", "Percent Accuracy"]]
        )
        summary_df = summary_df.reset_index().rename(columns={"Group": "Name"})
        summary_cols = [
            "Participant", "Condition", "Time",
            "ConditionType", "TargetPresence", "SetSize",
            "Name", "Accurate Responses", "Mean RT", "SD RT", "Percent Accuracy"
        ]
        summary_df = summary_df[summary_cols].sort_values(
            ["Participant", "Condition", "Time", "ConditionType", "TargetPresence", "SetSize"]
        ).reset_index(drop=True)

        st.success("✅ Analysis complete")
        st.dataframe(summary_df)

        # Attach stats to each raw row (far right)
        combined["Mean RT"] = combined["Group"].map(stats_df["Mean RT"])
        combined["SD RT"] = combined["Group"].map(stats_df["SD RT"])
        combined["Accurate Responses"] = combined["Group"].map(stats_df["Accurate Responses"])
        combined["Percent Accuracy"] = combined["Group"].map(stats_df["Percent Accuracy"])

        stat_cols = ["Mean RT", "SD RT", "Accurate Responses", "Percent Accuracy"]
        combined = combined[[c for c in combined.columns if c not in stat_cols] + stat_cols]

        # Download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="Summary")
            combined.to_excel(writer, index=False, sheet_name="Combined Raw")

        st.download_button(
            label="Download Excel (Summary + Raw)",
            data=output.getvalue(),
            file_name="visual_search_batch_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Upload multiple .csv/.xlsx files OR a ZIP containing them (subfolders allowed).")

# ===============================
# Stroop (multi-file/ZIP with .1/.2 pairing)
# ===============================
elif task_choice == "Stroop Task Data Analysis":
    st.header("Stroop Task Analyzer")

    col1, col2 = st.columns(2)
    with col1:
        stroop_files = st.file_uploader(
            "Upload ALL Stroop files (CSV/XLSX) — twins end with .1 / .2",
            type=["csv", "xlsx"],
            accept_multiple_files=True
        )
    with col2:
        stroop_zip = st.file_uploader("…or upload a ZIP containing folders/files", type=["zip"])

    def parse_stroop_meta(name: str):
        """
        Expect: P#_Stroop_CONDITION_TIMEPOINT[.1|.2].ext
        Returns (participant, condition_meta, time)
        """
        base = os.path.splitext(os.path.basename(name))[0]
        m = re.match(r"^(.*)\.(1|2)$", base)  # strip .1/.2 if present
        if m:
            base = m.group(1)
        parts = base.split("_")
        if len(parts) < 4:
            return None
        participant = parts[0].replace("P", "").strip()
        condition_meta = parts[2].upper().strip()
        time_label = map_time(parts[3])
        return participant, condition_meta, time_label

    def stroop_pair_key(name: str):
        """
        Create a pairing key by removing trailing .1/.2 before the extension.
        Files with the same key are twins.
        Example:
        P5_Stroop_CRL_PRE.1.csv -> key: p5_stroop_crl_pre.csv
        P5_Stroop_CRL_PRE.2.csv -> same key
        """
        path_base = os.path.basename(name)
        stem, ext = os.path.splitext(path_base)
        mm = re.match(r"^(.*)\.(1|2)$", stem)
        if mm:
            stem = mm.group(1)
        return f"{stem}{ext}".lower()

    def clean_stroop_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        # Use columns: C (index 2) = StimCondition, S(18), T(19), U(20)
        needed_idx = [2, 18, 19, 20]
        if max(needed_idx) >= df.shape[1]:
            return pd.DataFrame()
        sub = df.iloc[:, needed_idx].copy()
        sub.columns = ["StimCondition", "S", "T", "U"]
        return sub

    # Collect all candidate files as (name, bytes)
    files_bytes = []

    # A) loose files
    if stroop_files:
        for f in stroop_files:
            try:
                files_bytes.append((f.name, f.read()))
            except Exception as e:
                st.error(f"{f.name}: {e}")

    # B) ZIP (nested OK)
    if stroop_zip is not None:
        try:
            with ZipFile(stroop_zip) as zf:
                for member in zf.namelist():
                    if member.endswith("/"):
                        continue
                    ext = os.path.splitext(member)[1].lower()
                    if ext not in (".csv", ".xlsx"):
                        continue
                    with zf.open(member) as mf:
                        data = mf.read()
                    files_bytes.append((member, data))
        except Exception as e:
            st.error(f"ZIP error: {e}")

    if not files_bytes:
        st.info("Upload multiple .csv/.xlsx files OR a ZIP containing them (subfolders allowed).")
        st.stop()

    # Group by pair key
    from collections import defaultdict
    pairs = defaultdict(list)
    for name, data in files_bytes:
        pairs[stroop_pair_key(name)].append((name, data))

    all_rows = []
    warnings = []

    for key, items in pairs.items():
        # We expect twins (.1 and .2). If not exactly 2, warn but still process what exists.
        if len(items) != 2:
            warnings.append(f"Pair '{key}' has {len(items)} file(s); expected 2 (.1 and .2). Processing available files.")
        # parse meta from the key (works without .1/.2)
        meta = parse_stroop_meta(items[0][0])
        if not meta:
            warnings.append(f"Skipping (unrecognized name): {items[0][0]}")
            continue
        participant, condition_meta, time_label = meta

        # Read & concat available twins
        dfs = []
        for name, data in items:
            try:
                df = read_any_from_bytes(name, data, skiprows=3)
                dfs.append(df)
            except Exception as e:
                warnings.append(f"{name}: {e}")
        if not dfs:
            continue
        df_pair = pd.concat(dfs, ignore_index=True)

        # Clean/select columns, ignore timeouts
        sub = clean_stroop_dataframe(df_pair)
        if sub.empty:
            warnings.append(f"{items[0][0]}: not enough columns; skipped.")
            continue
        sub = sub[sub["S"].astype(str).str.lower() != "timeout"]

        # Types
        sub["StimCondition"] = sub["StimCondition"].astype(str).str.strip().str.lower()
        sub["T"] = pd.to_numeric(sub["T"], errors="coerce")
        sub["U"] = pd.to_numeric(sub["U"], errors="coerce")

        # Attach meta
        sub.insert(0, "Participant", participant)
        sub.insert(1, "Condition", condition_meta)
        sub.insert(2, "Time", time_label)

        all_rows.append(sub)

    if warnings:
        for w in warnings:
            st.warning(w)

    if not all_rows:
        st.error("No valid Stroop data found after pairing/cleaning.")
        st.stop()

    combined = pd.concat(all_rows, ignore_index=True)

    # Build Name: P#_Condition_Time_StimCondition
    # Also normalize StimCondition names for display
    def norm_stim(x):
        x = str(x).lower()
        if x == "congruent":
            return "Congruent"
        if x == "incongruent":
            return "Incongruent"
        if x == "doubly incongruent":
            return "Doubly Incongruent"
        return x.title()

    combined["StimConditionLabel"] = combined["StimCondition"].apply(norm_stim)

    combined["Name"] = (
        "P" + combined["Participant"].astype(str) + "_" +
        combined["Condition"].astype(str) + "_" +
        combined["Time"].astype(str) + "_" +
        combined["StimConditionLabel"]
    )

    # ---------- Stats per Name ----------
    grp = combined.groupby("Name", dropna=False)
    totals = grp.size().rename("Group_Total")
    correct_counts = grp["U"].apply(lambda s: (s == 1).sum()).rename("Accurate Responses")

    def rt_stats(g):
        g_corr = g[g["U"] == 1]
        return pd.Series({
            "Mean RT": g_corr["T"].mean(),
            "SD RT": g_corr["T"].std()
        })

    rt_df = grp.apply(rt_stats)
    stats_df = pd.concat([totals, correct_counts, rt_df], axis=1)
    stats_df["Percent Accuracy"] = (stats_df["Accurate Responses"] / stats_df["Group_Total"] * 100)

    # Round
    stats_df["Mean RT"] = stats_df["Mean RT"].round(2)
    stats_df["SD RT"] = stats_df["SD RT"].round(2)
    stats_df["Percent Accuracy"] = stats_df["Percent Accuracy"].round(2)

    # ---------- Summary with meta columns ----------
    meta_df = (
        combined.groupby("Name")
        .agg(
            Participant=("Participant", "first"),
            Condition=("Condition", "first"),
            Time=("Time", "first"),
            StimCondition=("StimConditionLabel", "first")
        )
    )

    summary_df = meta_df.join(
        stats_df[["Accurate Responses", "Mean RT", "SD RT", "Percent Accuracy"]]
    ).reset_index()  # Name becomes a column

    # Order columns
    summary_cols = [
        "Participant", "Condition", "Time",
        "StimCondition", "Name",
        "Accurate Responses", "Mean RT", "SD RT", "Percent Accuracy"
    ]
    summary_df = summary_df[summary_cols].sort_values(
        ["Participant", "Condition", "Time", "StimCondition"]
    ).reset_index(drop=True)

    st.success("✅ Analysis complete")
    st.dataframe(summary_df)

    # ---------- Attach stats to raw combined (far right) ----------
    combined["Mean RT"] = combined["Name"].map(stats_df["Mean RT"])
    combined["SD RT"] = combined["Name"].map(stats_df["SD RT"])
    combined["Accurate Responses"] = combined["Name"].map(stats_df["Accurate Responses"])
    combined["Percent Accuracy"] = combined["Name"].map(stats_df["Percent Accuracy"])

    # Move stat cols to the end
    stat_cols = ["Mean RT", "SD RT", "Accurate Responses", "Percent Accuracy"]
    combined = combined[[c for c in combined.columns if c not in stat_cols] + stat_cols]

    # ---------- Export ----------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        combined.to_excel(writer, index=False, sheet_name="Combined Raw")

    st.download_button(
        label="📥 Download Full Excel Report",
        data=output.getvalue(),
        file_name="stroop_batch_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )







