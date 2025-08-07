import streamlit as st
import pandas as pd
import io
import os

st.title("Cognitive Task Data Analyzer")

task_choice = st.selectbox("Choose a program:", [
    "Visual Search Task Data Analysis",
    "Stroop Task Data Analysis"
])

if task_choice == "Visual Search Task Data Analysis":
    st.header("Visual Search Task")
    uploaded_file = st.file_uploader("Upload your data file", type=["csv", "xlsx"])

    if uploaded_file:
        try:
            ext = os.path.splitext(uploaded_file.name)[1]
            if ext == ".csv":
                df = pd.read_csv(uploaded_file, skiprows=3)
            elif ext == ".xlsx":
                df = pd.read_excel(uploaded_file, skiprows=3)
            else:
                raise ValueError("Unsupported file type")

            df = df.iloc[:, [18, 19]]
            df.columns = ['ResponseTime', 'Correct']
            df_correct = df[df['Correct'] == 1]

            mean_rt = df_correct['ResponseTime'].mean()
            std_rt = df_correct['ResponseTime'].std()
            num_correct = len(df_correct)
            percent_accuracy = (num_correct / 80) * 100

            result_df = pd.DataFrame({
                'Mean RT': [mean_rt],
                'SD RT': [std_rt],
                'Accurate Responses': [num_correct],
                'Percent Accuracy': [percent_accuracy]
            })

            st.success("✅ Analysis complete")
            st.dataframe(result_df)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                result_df.to_excel(writer, index=False)
            st.download_button(
                label="Download Excel File",
                data=output.getvalue(),
                file_name='visual_search_results.xlsx',
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

            # Split into three groups
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

