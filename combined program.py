import streamlit as st
import pandas as pd
import io
import os

st.title("Cognitive Task Data Analyzer")

task_choice = st.selectbox(
    "Choose a program:",
    ["Visual Search Task Data Analysis", "Stroop Task Data Analysis"]
)

# -------------------------------
# Common helpers
# -------------------------------
def read_any(file, skiprows=3):
    ext = os.path.splitext(file.name)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file, skiprows=skiprows)
    elif ext == ".xlsx":
        return pd.read_excel(file, skiprows=skiprows, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def map_time(raw):
    raw = str(raw).upper()
    if raw == "POST1":
        return "POST15"
    if raw == "POST2":
        return "POST30"
    return raw

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

    def parse_filename(name: str):
        """
        Expect: P#_VisualSearch_CONDITION_TIMEPOINT.ext
        Works even if nested path like sub/dir/P8_VisualSearch_CRL_PRE.csv
        """
        base = os.path.splitext(os.path.basename(name))[0]
        parts = base.split("_")
        if len(parts) < 4:
            return None
        participant = parts[0].replace("P", "").strip()
        # parts[1] is usually 'VisualSearch' - we ignore it
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

    # A) handle multiple loose files
    if uploaded_files:
        for uf in uploaded_files:
            meta = parse_filename(uf.name)
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

    # B) handle ZIP (nested folders OK)
    if zip_file is not None:
        from zipfile import ZipFile
        from io import BytesIO
        try:
            with ZipFile(zip_file) as zf:
                for member in zf.namelist():
                    if member.endswith("/"):
                        continue
                    ext = os.path.splitext(member)[1].lower()
                    if ext not in (".csv", ".xlsx"):
                        continue
                    meta = parse_filename(member)
                    if not meta:
                        st.warning(f"Skipping unrecognized file name in ZIP: {member}")
                        continue
                    participant, condition, time_label = meta

                    with zf.open(member) as f:
                        if ext == ".csv":
                            df = pd.read_csv(f, skiprows=3)
                        else:
                            df = pd.read_excel(BytesIO(f.read()), skiprows=3, engine="openpyxl")

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

    # Continue only if we gathered rows
    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True)

        # Build grouping pieces
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

        # Numeric + drop rows missing key inputs
        combined["Correct"] = pd.to_numeric(combined["Correct"], errors="coerce")
        combined["ResponseTime"] = pd.to_numeric(combined["ResponseTime"], errors="coerce")
        combined = combined.dropna(subset=["ConditionLabel", "PresenceLabel", "SetSize"])

        # NEW: Group label you wanted
        # P<participant>_<Condition>_<Time>_<Feature/Conj>_<P/A>_<SetSize>
        combined["Group"] = (
            "P" + combined["Participant"].astype(str) + "_" +
            combined["Condition"].astype(str) + "_" +
            combined["Time"].astype(str) + "_" +
            combined["ConditionLabel"] + "_" +
            combined["PresenceLabel"] + "_" +
            combined["SetSize"]
        )

        # ---------- Compute per-group stats ----------
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

        # ---------- Summary shown in the app ----------
        result_df = stats_df.reset_index().rename(columns={"Group": "Condition"})
        st.success("✅ Analysis complete")
        st.dataframe(result_df.sort_values("Condition", ignore_index=True))

        # ---------- Attach stats to EVERY raw row (rightmost) ----------
        combined["Mean RT"] = combined["Group"].map(stats_df["Mean RT"])
        combined["SD RT"] = combined["Group"].map(stats_df["SD RT"])
        combined["Accurate Responses"] = combined["Group"].map(stats_df["Accurate Responses"])
        combined["Percent Accuracy"] = combined["Group"].map(stats_df["Percent Accuracy"])

        # Move stat columns to the far right
        stat_cols = ["Mean RT", "SD RT", "Accurate Responses", "Percent Accuracy"]
        combined = combined[[c for c in combined.columns if c not in stat_cols] + stat_cols]

        # ---------- Export ----------
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="Summary")
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
# Stroop (unchanged: two files)
# ===============================
elif task_choice == "Stroop Task Data Analysis":
    st.header("Stroop Task Analyzer")

    uploaded_file1 = st.file_uploader("Upload First Data File", type=["csv", "xlsx"], key="stroop1")
    uploaded_file2 = st.file_uploader("Upload Second Data File", type=["csv", "xlsx"], key="stroop2")

    if uploaded_file1 and uploaded_file2:
        try:
            def clean_file(file):
                df = read_any(file, skiprows=3)
                df = df.iloc[:, [2, 18, 19, 20]].copy()
                df.columns = ["Condition", "S", "T", "U"]
                return df

            df1 = clean_file(uploaded_file1)
            df2 = clean_file(uploaded_file2)
            combined_df = pd.concat([df1, df2], ignore_index=True)

            combined_df = combined_df[combined_df["S"].astype(str).str.lower() != "timeout"]
            combined_df["Condition"] = combined_df["Condition"].astype(str)
            combined_df["S"] = combined_df["S"].astype(str)
            combined_df["T"] = pd.to_numeric(combined_df["T"], errors="coerce")
            combined_df["U"] = pd.to_numeric(combined_df["U"], errors="coerce")

            groups = [
                ("Congruent", combined_df[combined_df["Condition"].str.lower() == "congruent"].copy()),
                ("Incongruent", combined_df[combined_df["Condition"].str.lower() == "incongruent"].copy()),
                ("Doubly Incongruent", combined_df[combined_df["Condition"].str.lower() == "doubly incongruent"].copy())
            ]

            results = []
            for group_name, group_df in groups:
                total = len(group_df)
                correct_df = group_df[group_df["U"] == 1]
                num_correct = len(correct_df)
                pct_acc = (num_correct / total * 100) if total else 0.0
                mean_rt = correct_df["T"].mean()
                sd_rt = correct_df["T"].std()

                results.append({
                    "Condition": group_name,
                    "Mean RT": round(mean_rt, 2) if pd.notna(mean_rt) else None,
                    "SD RT": round(sd_rt, 2) if pd.notna(sd_rt) else None,
                    "Accurate Responses": int(num_correct),
                    "Percent Accuracy": round(pct_acc, 2)
                })

            result_df = pd.DataFrame(results)

            st.success("✅ Analysis complete!")
            st.dataframe(result_df)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                result_df.to_excel(writer, index=False, sheet_name="Summary")
                combined_df.to_excel(writer, index=False, sheet_name="Combined Raw")

            st.download_button(
                label="📥 Download Full Excel Report",
                data=output.getvalue(),
                file_name="stroop_analysis_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"❌ Error: {e}")






