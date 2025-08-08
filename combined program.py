import streamlit as st
import pandas as pd
import io
import os

st.title("Cognitive Task Data Analyzer")

task_choice = st.selectbox("Choose a program:", [
    "Visual Search Task Data Analysis",
    "Stroop Task Data Analysis"
])

def process_visual_search_folder(folder_path):
    all_data = []

    for filename in os.listdir(folder_path):
        if filename.endswith(".csv") or filename.endswith(".xlsx"):
            try:
                name_parts = os.path.splitext(filename)[0].split("_")
                if len(name_parts) != 4:
                    continue
                participant = name_parts[0].replace("P", "")
                condition = name_parts[2].upper()
                time_raw = name_parts[3].upper()

                if time_raw == "POST1":
                    time = "POST15"
                elif time_raw == "POST2":
                    time = "POST30"
                else:
                    time = time_raw

                file_path = os.path.join(folder_path, filename)

                if filename.endswith(".csv"):
                    df = pd.read_csv(file_path, skiprows=3)
                else:
                    df = pd.read_excel(file_path, skiprows=3)

                selected = df.iloc[:, [3, 4, 5, 18, 19]]
                selected.columns = ['TargetPresence', 'SearchType', 'SetSize', 'ResponseTime', 'Correct']
                selected.insert(0, 'Time', time)
                selected.insert(0, 'Condition', condition)
                selected.insert(0, 'Participant', participant)
                all_data.append(selected)
            except Exception as e:
                print(f"❌ Failed to process {filename}: {e}")

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()

if task_choice == "Visual Search Task Data Analysis":
    st.header("Visual Search Task")
    folder_path = st.text_input("Enter folder path containing Visual Search files:")

    if folder_path and os.path.isdir(folder_path):
        try:
            df = process_visual_search_folder(folder_path)

            if df.empty:
                st.warning("No valid files found in the folder.")
            else:
                df['SetSize'] = df['SetSize'].astype(str).str[:2]
                df['ConditionLabel'] = df['SearchType'].str.strip().str.lower().map({
                    'feature': 'Feature',
                    'conjunction': 'Conj'
                })
                df['PresenceLabel'] = df['TargetPresence'].str.strip().str.lower().map({
                    'present': 'P',
                    'absent': 'A'
                })

                df = df.dropna(subset=['ConditionLabel', 'PresenceLabel', 'SetSize'])
                df['Group'] = df['ConditionLabel'] + '_' + df['PresenceLabel'] + '_' + df['SetSize']
                df['Correct'] = pd.to_numeric(df['Correct'], errors='coerce')
                df['ResponseTime'] = pd.to_numeric(df['ResponseTime'], errors='coerce')

                results = []
                for group_name, group_df in df.groupby('Group'):
                    total = len(group_df)
                    correct_df = group_df[group_df['Correct'] == 1]
                    num_correct = len(correct_df)
                    percent_accuracy = (num_correct / total) * 100 if total else 0
                    mean_rt = correct_df['ResponseTime'].mean()
                    sd_rt = correct_df['ResponseTime'].std()

                    results.append({
                        'Condition': group_name,
                        'Mean RT': round(mean_rt, 2),
                        'SD RT': round(sd_rt, 2),
                        'Accurate Responses': num_correct,
                        'Percent Accuracy': round(percent_accuracy, 2)
                    })

                result_df = pd.DataFrame(results)
                st.success("✅ Analysis complete")
                st.dataframe(result_df)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    result_df.to_excel(writer, index=False)
                st.download_button(
                    label="Download Excel File",
                    data=output.getvalue(),
                    file_name='visual_search_results_detailed.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )

        except Exception as e:
            st.error(f"❌ Error: {e}")

elif task_choice == "Stroop Task Data Analysis":
    st.header("Stroop Task Analyzer")
    uploaded_file1 = st.file_uploader("Upload First Data File", type=["csv", "xlsx"], key="stroop1")
    uploaded_file2 = st.file_uploader("Upload Second Data File", type=["csv", "xlsx"], key="stroop2")

    if uploaded_file1 and uploaded_file2:
        try:
            def clean_file(file):
                ext = os.path.splitext(file.name)[1]
                if ext == ".csv":
                    df = pd.read_csv(file, skiprows=3, engine="python")
                elif ext == ".xlsx":
                    df = pd.read_excel(file, skiprows=3, engine="openpyxl")
                else:
                    raise ValueError("Unsupported file type")
                df = df.iloc[:, [2, 18, 19, 20]]
                df.columns = ['Condition', 'S', 'T', 'U']
                return df

            df1 = clean_file(uploaded_file1)
            df2 = clean_file(uploaded_file2)
            combined_df = pd.concat([df1, df2], ignore_index=True)

            combined_df = combined_df[combined_df['S'].astype(str).str.lower() != "timeout"]

            combined_df['Condition'] = combined_df['Condition'].astype(str)
            combined_df['S'] = combined_df['S'].astype(str)
            combined_df['T'] = pd.to_numeric(combined_df['T'], errors='coerce')
            combined_df['U'] = pd.to_numeric(combined_df['U'], errors='coerce')

            congruent_df = combined_df[combined_df['Condition'].str.lower() == 'congruent'].copy()
            incongruent_df = combined_df[combined_df['Condition'].str.lower() == 'incongruent'].copy()
            doubly_incongruent_df = combined_df[combined_df['Condition'].str.lower() == 'doubly incongruent'].copy()

            congruent_df['Group'] = 'Congruent'
            incongruent_df['Group'] = 'Incongruent'
            doubly_incongruent_df['Group'] = 'Doubly Incongruent'

            results = []
            for group_name, group_df in [
                ('Congruent', congruent_df),
                ('Incongruent', incongruent_df),
                ('Doubly Incongruent', doubly_incongruent_df)
            ]:
                group_total = len(group_df)
                group_correct_df = group_df[group_df['U'] == 1]
                num_correct = len(group_correct_df)
                percent_accuracy = (num_correct / group_total) * 100 if group_total else 0
                mean_rt = group_correct_df['T'].mean()
                sd_rt = group_correct_df['T'].std()

                results.append({
                    'Condition': group_name,
                    'Mean RT': round(mean_rt, 2),
                    'SD RT': round(sd_rt, 2),
                    'Accurate Responses': num_correct,
                    'Percent Accuracy': round(percent_accuracy, 2)
                })

            result_df = pd.DataFrame(results)

            st.success("✅ Analysis complete!")
            st.dataframe(result_df)

            final_df = pd.concat([result_df, combined_df], ignore_index=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False)

            st.download_button(
                label="📥 Download Full Excel Report",
                data=output.getvalue(),
                file_name="stroop_analysis_output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"❌ Error: {e}")

