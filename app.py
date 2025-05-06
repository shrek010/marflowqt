# streamlit run app.py 
# pip freeze > requirements.txt

import streamlit as st
import pandas as pd
from packaging_list_parser import parse_packaging_list
from coa_parser import parse_certificate_of_analysis
from match_coa_to_packing_list import validate_against_packaging_list
from sterilization_cert import parse_sterilization_certificate  
from validate_sc import validate_sc_against_sources
import smtplib
from email.message import EmailMessage
from io import StringIO



st.set_page_config(page_title="QC Validator", layout="centered")
st.title("📦 Marflow QC Validator Tool")
st.markdown("""
Welcome to the Quality Control Validator.
Please upload the **Packing List** to begin.
""")

def login():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        password = st.text_input("Enter password:", type="password")
        if password == "mfl123":
            st.session_state["authenticated"] = True
            st.rerun()
        elif password:
            st.warning("Wrong password")
        st.stop()

login()

# Upload Packing List
uploaded_file = st.file_uploader("Upload Packing List (Excel)", type=["xlsx", "xls"])
if uploaded_file:
    df, extracted_items = parse_packaging_list(uploaded_file)
    if df is not None:
        st.success("✅ Packing List Loaded")
        st.subheader("🔍 Extracted Item Info")
        st.dataframe(extracted_items)
        st.session_state["packaging_list"] = extracted_items
    else:
        st.error("❌ Failed to parse the uploaded file.")

# Upload multiple COAs
if "packaging_list" in st.session_state:
    st.subheader("📄 Upload One or More COA PDFs")
    coa_files = st.file_uploader("Upload COAs", type=["pdf"], accept_multiple_files=True, key="multi_coa")
    if coa_files:
        all_coa_results = []
        for file in coa_files:
            coa_data = parse_certificate_of_analysis(file)
            if coa_data:
                result_df = validate_against_packaging_list(coa_data, st.session_state["packaging_list"])
                result_df["COA File"] = file.name
                all_coa_results.append(result_df)
            else:
                st.error(f"❌ Could not extract data from `{file.name}`")

        if all_coa_results:
            st.markdown("## 📋 COA Validation Results")
            final_coa_table = pd.concat(all_coa_results, ignore_index=True)
            total_checks = final_coa_table.shape[0]
            total_matches = (final_coa_table["Match"] == "✅").sum()
            total_mismatches = (final_coa_table["Match"] == "❌").sum()
            st.success(f"Total Fields Checked: {total_checks}")
            st.info(f"✅ Matches: {total_matches}")
            st.error(f"❌ Mismatches: {total_mismatches}")

            def highlight_mismatches(val):
                if val == "❌":
                    return "color: red; font-weight: bold;"
                if val == "✅":
                    return "color: green; font-weight: bold;"
                return ""

            styled_table = final_coa_table.style.applymap(
                highlight_mismatches,
                subset=["Match"]
            )

            with st.expander("🔍 View Detailed COA Validation Table", expanded=True):
                st.dataframe(styled_table, use_container_width=True)

            st.download_button(
                "⬇️ Download COA Validation Report as CSV",
                final_coa_table.to_csv(index=False),
                file_name="coa_validation_report.csv",
                mime="text/csv"
            )

# Upload Sterilization Certificates
if "packaging_list" in st.session_state:
    st.subheader("🧼 Upload Sterilization Certificates (PDFs)")
    sc_files = st.file_uploader("Upload SC PDFs", type=["pdf"], accept_multiple_files=True, key="multi_sc")
    if sc_files:
        sc_results = []
        for file in sc_files:
            sc_data_list = parse_sterilization_certificate(file)
            if sc_data_list:
                sc_results.extend(sc_data_list)
            else:
                st.error(f"❌ Could not extract data from `{file.name}`")

        # Validate SCs only against Packing List
        if sc_results:
            st.markdown("## 📋 SC Validation Results")
            all_validations = []
            for sc in sc_results:
                validation_df = validate_sc_against_sources(
                    sc,
                    st.session_state["packaging_list"]
                )
                validation_df["SC Certificate"] = sc.get("Batch No", "Unknown")
                all_validations.append(validation_df)

            if all_validations:
                combined_validation = pd.concat(all_validations, ignore_index=True)
                combined_validation = combined_validation.astype(str)
                total_checks = combined_validation.shape[0]
                total_matches = (combined_validation["Validation"] == "✅").sum()
                total_mismatches = (combined_validation["Validation"] == "❌").sum()
                st.success(f"Total Fields Checked: {total_checks}")
                st.info(f"✅ Matches: {total_matches}")
                st.error(f"❌ Mismatches: {total_mismatches}")

                def highlight_discrepancies(val):
                    if isinstance(val, str) and val.startswith("❌"):
                        return "color: red; font-weight: bold;"
                    if isinstance(val, str) and val.startswith("✅"):
                        return "color: green; font-weight: bold;"
                    return ""

                styled_combined = combined_validation.style.applymap(
                    highlight_discrepancies,
                    subset=["SC Value", "Expected Value"]
                )

                # Show only detailed table
                with st.expander("🔍 View Detailed Validation Table", expanded=True):
                    st.dataframe(styled_combined, use_container_width=True)

                # Download CSV
                csv = combined_validation.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Download SC Validation Report as CSV",
                    data=csv,
                    file_name="sc_validation_report.csv",
                    mime="text/csv"
                )
                
def send_email_report(to_email, concise_df, sender_email, sender_password, smtp_server="smtp.gmail.com", smtp_port=587):
    msg = EmailMessage()
    msg["Subject"] = "Validation Report"
    msg["From"] = sender_email
    msg["To"] = to_email
    msg.set_content("Please find attached the concise mismatch report from Marflow QC Validator.")
    csv_buffer = StringIO()
    concise_df.to_csv(csv_buffer, index=False)
    csv_bytes = csv_buffer.getvalue().encode('utf-8')
    msg.add_attachment(csv_bytes, maintype="application", subtype="csv", filename="mismatch_report.csv")

    with smtplib.SMTP(smtp_server, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(sender_email, sender_password)
        smtp.send_message(msg)
     
# 📌 Build a concise mismatch-only table from both COA and SC
# 📌 Build final merged table in client-desired format
if "packaging_list" in st.session_state:
    if 'final_coa_table' in locals() and 'combined_validation' in locals():
        ref_lookup = st.session_state["packaging_list"].set_index("Batch No")["Ref Code"].to_dict()
        coa_data = final_coa_table[final_coa_table["Match"] == "❌"].copy()
        coa_data["Ref code"] = coa_data["Batch No"].map(ref_lookup).fillna("Not mention")
        coa_data["COA"] = coa_data["Field"] + ": " + coa_data["COA Value"].astype(str)
        coa_data["Packing list"] = coa_data["Field"] + ": " + coa_data["Expected Value"].astype(str)
        coa_data["EtO Sterilization certificate"] = "--"
        coa_data = coa_data[["Ref code", "Batch No", "EtO Sterilization certificate", "COA", "Packing list"]]
        sc_data = combined_validation[combined_validation["Validation"] == "❌"].copy()
        sc_data["Ref code"] = sc_data["Batch No"].map(ref_lookup).fillna("Not mention")
        sc_data["EtO Sterilization certificate"] = sc_data.apply(lambda row: f"{row['Field']}: {row['SC Value'].replace('❌','').replace('✅','').strip()}", axis=1)
        sc_data["Packing list"] = sc_data.apply(lambda row: f"{row['Field']}: {row['Expected Value'].replace('❌','').replace('✅','').strip()}", axis=1)
        sc_data["COA"] = "--"
        sc_data = sc_data[["Ref code", "Batch No", "EtO Sterilization certificate", "COA", "Packing list"]]
        final_client_format = pd.concat([coa_data, sc_data], ignore_index=True)
        st.markdown("## 📋 Client Format Final Table")
        st.dataframe(final_client_format, use_container_width=True)
        st.download_button(
            label="⬇️ Download Report as CSV",
            data=final_client_format.to_csv(index=False),
            file_name="final_client_report.csv",
            mime="text/csv")


        from io import BytesIO
        from openpyxl.styles import Font, Alignment
        from openpyxl.utils.dataframe import dataframe_to_rows
        from openpyxl import Workbook

        # Create workbook and sheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Report"

        # Add DataFrame rows to worksheet
        for r_idx, row in enumerate(dataframe_to_rows(final_client_format, index=False, header=True), 1):
            ws.append(row)
            for c_idx, cell in enumerate(ws[r_idx], 1):
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if r_idx == 1:
                    cell.font = Font(bold=True)

        # Optional: Auto-adjust column widths
        for column_cells in ws.columns:
            length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = length + 3

        # Save to in-memory buffer
        excel_buffer = BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)

        # Streamlit download button
        st.download_button(
            label="⬇️ Download Final Report as Excel",
            data=excel_buffer.getvalue(),
            file_name="final_client_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )



        
        
# # ✅ Show only if the concise table exists
# if "packaging_list" in st.session_state:
#     if 'final_coa_table' in locals() and 'combined_validation' in locals():
#         # [same code for building concise_mismatches table here]

#         if not concise_mismatches.empty:
#             with st.expander("🔍 Concise Mismatch Summary Table", expanded=True):
#                 st.dataframe(concise_mismatches, use_container_width=True)

#             st.download_button(
#                 label="⬇️ Download Concise Mismatch Table",
#                 data=concise_mismatches.to_csv(index=False),
#                 file_name="concise_mismatch_report.csv",
#                 mime="text/csv",
#                 key="download_concise_mismatch"
#             )
