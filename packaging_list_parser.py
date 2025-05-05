import pandas as pd
import re
import zipfile
import tempfile
from io import BytesIO

def strip_styles_from_excel(uploaded_file):
    """
    Removes styles.xml from the uploaded Excel file (to fix formatting issues).
    Returns path to a clean temporary Excel file.
    """
    in_memory = BytesIO(uploaded_file.getvalue())
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        with zipfile.ZipFile(in_memory) as zin:
            with zipfile.ZipFile(tmp.name, "w") as zout:
                for item in zin.infolist():
                    if item.filename != "xl/styles.xml":
                        zout.writestr(item, zin.read(item.filename))
        return tmp.name


def extract_normalized_size(desc):
    desc = str(desc).upper().replace("\n", " ").replace("\r", " ").strip()

    # Match CH or CH ranges like CH 7, CH7-10, CH 7 TO 10, CH 8.5
    ch_match = re.search(r"\bCH\s*\d+(\.\d+)?(\s*[-–TO/]+\s*CH?\s*\d+(\.\d+)?)?\b", desc)
    ch_clean = None
    if ch_match:
        ch_raw = ch_match.group().replace("TO", "-").replace("–", "-").replace("/", "-").replace("+", "-")
        nums = re.findall(r"\d+(?:\.\d+)?", ch_raw)
        if len(nums) == 2:
            ch_clean = f"CH{nums[0]}-{nums[1]}"
        elif len(nums) == 1:
            ch_clean = f"CH{nums[0]}"

    # Extract cm with decimal
    cm_match = re.search(r"\d+(\.\d+)?\s*CM", desc)
    cm_clean = cm_match.group().replace(" ", "").upper() if cm_match else None

    # Extract Gauge with decimal (rare, but being safe)
    g_match = re.search(r"\d+(\.\d+)?\s*G", desc)
    g_clean = g_match.group().replace(" ", "").upper() if g_match else None

    size_parts = []
    if g_clean:
        size_parts.append(g_clean)
    if ch_clean:
        size_parts.append(ch_clean)
    if cm_clean:
        size_parts.append(cm_clean)

    return " x ".join(size_parts) if size_parts else "N/A"

def parse_packaging_list(uploaded_file):
    try:
        clean_file_path = strip_styles_from_excel(uploaded_file)

        df_raw = pd.read_excel(clean_file_path, 
                               engine="openpyxl", 
                               sheet_name="PACKING LIST", 
                               header=None)

        header_row = 21
        columns = df_raw.iloc[header_row].fillna("").astype(str).str.strip().tolist()
        df_data = df_raw.iloc[header_row + 1:].copy()
        df_data.columns = columns
        df_data = df_data.reset_index(drop=True)
        df_data = df_data[df_data["Sl. No. of Item"].notna()]

        extracted = []
        for idx, row in df_data.iterrows():
            full_desc = str(row.get("Description of Goods", "")).strip()
            normalized_size = extract_normalized_size(full_desc)

            # Remove size parts from the description
            cleaned_desc = re.sub(r"\bCH\s*\d+.*?(?=[,\s]|$)", "", full_desc, flags=re.IGNORECASE)
            cleaned_desc = re.sub(r"\d+\s*CM", "", cleaned_desc, flags=re.IGNORECASE)
            cleaned_desc = re.sub(r"\d+\s*G", "", cleaned_desc, flags=re.IGNORECASE)
            cleaned_desc = re.sub(r"[-+]", "", cleaned_desc)
            cleaned_desc = re.sub(r"\s+", " ", cleaned_desc).strip(" ,")

            extracted.append({
                "Sr. No.": int(row.get("Sl. No. of Item")),
                "Description": cleaned_desc,
                "Size": normalized_size,
                "Ref Code": str(row.get("Ref. code", "")).strip(),
                "Qty": row.get("Qty          (In Nos)", ""),
                "Batch No": str(row.get("BATCH NO", "")).strip(),
                "MFG Date": str(row.get("MFG DATE", "")).strip(),  
                "EXP Date": str(row.get("EXP DATE", "")).strip()   
            })

        return df_data, pd.DataFrame(extracted)

    except Exception as e:
        print(f"❌ Packing List Parsing Failed: {e}")
        return None, None
