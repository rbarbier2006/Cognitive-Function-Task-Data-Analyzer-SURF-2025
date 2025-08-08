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
# Helpers
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
# Visual Search (multi-file)
# ===============================
if task_choice == "Visual Search Task Data Analysis":
    st.header("Visual Search Task")

    uploaded_files = st.file_uploader(
        "Upload ALL Visual Search files (CSV/XLSX) at once",
        type=["csv", "xlsx"],
        accept_multiple_files=True
    )

    if uploaded_files:
        try:
            all_rows = []

            for uf in uploaded_files:
                # File name format: P#_VisualSearch_CONDITION_TIMEPOINT.ext
                base = os.path.splitext(uf.name)[0]
                parts = base.split("_")
                # be tolerant of names like "P8 (5) CONTRAST - VS" -> skip, or adjust if needed
                if len(parts) < 4:
                    # Try a more tolerant parse: look for the first piece that starts with P, etc.
                    # If it still doesn't match, skip gracefully
                    st.warning(f"Skipping unrecognized file name: {uf.name}")
                    continue

                participant = parts[0].replace("P", "").strip()
                # parts[1] is "VisualSearch" ideally; ignore/casual check
                condition = parts[2].upper().strip()
                time_label = map_time(parts[3])

                df = read_any(uf, skiprows=3)

                # Select columns: D, E, F, S, T  -> by index: 3, 4, 5, 18, 19
                # Guard in case sheet has fewer columns
                needed_idx = [3, 4, 5, 18, 19]
                if max(needed_idx) >= df.shape[1]:
                    st.warning(f"{uf.name}: not enough columns after skiprows=3; skipping.")
                    continue

                sub = df.iloc[:, needed_idx].copy()
                sub.columns = ["TargetPresence", "SearchType", "SetSizeRaw", "ResponseTime", "Correct"]

                # Attach metadata from filename
                sub.insert(0, "Participant", participant)
                sub.insert(1, "Condition", condition)
                sub.insert(2, "Time", time_label)

                all_rows.append(sub)

            if not all_rows:
                st.warning("No valid files were processed.")
                st.stop()

            combined = pd.concat(all_rows, ignore_index=True)

            # ---- Grouping logic: Feature/Conj, Present/Absent, SetSize (first 2 chars) ----
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

            # Clean numeric
            combined["Correct"] = pd.to_numeric(combined["Correct"], errors="coerce")
            combined["ResponseTime"] = pd.to_numeric(combined["ResponseTime"], errors="coerce")

            # Drop rows missing grouping pieces
            combined = combined.dropna(subset=["ConditionLabel", "PresenceLabel", "SetSize"])

            # Final group key like Feature_P_04, Conj_A_32, etc.
            combined["Group"] = combined["ConditionLabel"] + "_" + combined["PresenceLabel"] + "_" + combined["SetSize"]

            # Compute stats per group
            results = []
            for group_name, g in combined.groupby("Group"):
                total = len(g)
                correct_g = g[g["Correct"] == 1]
                num_correct = len(correct_g)
                pct_acc = (num_correct / total * 100) if total else 0.0
                mean_rt = correct_g["ResponseTime"].mean()
                sd_rt = correct_g["ResponseTime"].std()

                results.append({
                    "Condition": group_name,
                    "Mean RT": round(mean_rt, 2) if pd.notna(mean_rt) else None,
                    "SD RT": round(sd_rt, 2) if pd.notna(sd_rt) else None,
                    "Accurate Responses": int(num_correct),
                    "Percent Accuracy": round(pct_acc, 2)
                })

            result_df = pd.DataFrame(results).sort_values("Condition", ignore_index=True)

            st.success("✅ Analysis complete")
            st.dataframe(result_df)

            # Export: summary + raw combined (optional)
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

        except Exception as e:
            st.error(f"❌ Error: {e}")

# ===============================
# Stroop (unchanged – two files)
# ===============================
elif task_choice == "Stroop Task Data Analysis":
    st.header("Stroop Task Analyzer")

    uploaded_file1 = st.file_uploader("Upload First Data File", type=["csv", "xlsx"], key="stroop1")
    uploaded_file2 = st.file_uploader("Upload Second Data File", type=["csv", "xlsx"], key="stroop2")

    if uploaded_file1 and uploaded_file2:
        try:
            def clean_file(file):
                df = read_any(file, skiprows=3)   # you were on skiprows=3 after your fix
                df = df.iloc[:, [2, 18, 19, 20]].copy()
                df.columns = ["Condition", "S", "T", "U"]
                return df

            df1 = clean_file(uploaded_file1)
            df2 = clean_file(uploaded_file2)
            combined_df = pd.concat([df1, df2], ignore_index=True)

            # Remove timeouts
            combined_df = combined_df[combined_df["S"].astype(str).str.lower() != "timeout"]

            # Types
            combined_df["Condition"] = combined_df["Condition"].astype(str)
            combined_df["S"] = combined_df["S"].astype(str)
            combined_df["T"] = pd.to_numeric(combined_df["T"], errors="coerce")
            combined_df["U"] = pd.to_numeric(combined_df["U"], errors="coerce")

            # Split into three
            groups = [
                ("Congruent", combined_df[combined_df["Condition"].str.lower() == "congruent"].copy()),
                ("Incongruent", combined_df[combined_df["Condition"].str.lower() == "incongruent"].copy()),
                ("Doubly Incongruent", combined_df[combined_df["Condition"].str.lower() == "doubly incongruent"].copy())
            ]
            for name, g in groups:
                g["Group"] = name

            results = []
            for group_name, group_df in groups:
                total = len(group_df)
                group_correct_df = group_df[group_df["U"] == 1]
                num_correct = len(group_correct_df)
                pct_acc = (num_correct / total * 100) if total else 0.0
                mean_rt = group_correct_df["T"].mean()
                sd_rt = group_correct_df["T"].std()

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



