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
            percent_accuracy = num_correct / 80

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
                    df = pd.read_csv(file, skiprows=4, engine="python")
                elif ext == ".xlsx":
                    df = pd.read_excel(file, skiprows=4, engine="openpyxl")
                else:
                    raise ValueError("Unsupported file type")
                df = df.iloc[:, [18, 19, 20]]
                df.columns = ['S', 'T', 'U']
                return df

            df1 = clean_file(uploaded_file1)
            df2 = clean_file(uploaded_file2)
            combined_df = pd.concat([df1, df2], ignore_index=True)

            combined_df['S'] = combined_df['S'].astype(str)
            combined_df['U'] = pd.to_numeric(combined_df['U'], errors='coerce')
            combined_df['T'] = pd.to_numeric(combined_df['T'], errors='coerce')

            correct_df = combined_df[combined_df['U'] == 1]
            num_correct = len(correct_df)
            total_responses = len(combined_df)
            percent_accuracy = num_correct / total_responses if total_responses else 0

            mean_rt = correct_df['T'].mean()
            sd_rt = correct_df['T'].std()

            result_df = pd.DataFrame([{
                "Mean RT": round(mean_rt, 2),
                "SD RT": round(sd_rt, 2),
                "Accurate Responses": num_correct,
                "Percent Accuracy": round(percent_accuracy, 4)
            }])

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
