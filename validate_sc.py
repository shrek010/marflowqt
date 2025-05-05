import pandas as pd
import re
from dateutil import parser

def normalize_size(size_str):
    """
    Normalize size field so CH20, 20CH, 20 Ch all match.
    """
    size_str = str(size_str).upper().strip()
    size_str = size_str.replace(" ", "")
    size_str = size_str.replace("CH", "").replace("CM", "").replace("MM", "")
    digits = ''.join(filter(str.isdigit, size_str))
    if digits:
        return f"CH{digits}"
    return size_str

def normalize_product_name(text):
    """
    Normalize product name to ignore case, spaces, special characters.
    """
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9]", "", text)  # Remove everything except letters/numbers
    return text

def normalize_date(date_str):
    """
    Normalize all dates to YYYY-MM format.
    Works for formats like 'Feb 2025', '2025-02', '01/2025', etc.
    """
    date_str = str(date_str).strip()
    if not date_str:
        return ""
    try:
        dt = parser.parse(date_str, fuzzy=True)
        return dt.strftime("%Y-%m")
    except Exception:
        match = re.match(r"(\d{4})[-/ ]?(\d{1,2})", date_str)
        if match:
            year, month = match.groups()
            return f"{year}-{int(month):02d}"
        return date_str.upper()

def validate_sc_against_sources(sc_data: dict, packing_list_df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate SC data against Packing List only and report detailed mismatches.
    """
    batch_no = str(sc_data.get("Batch No", "")).strip()
    packing_match = packing_list_df[packing_list_df["Batch No"].astype(str).str.strip() == batch_no]
    
    if packing_match.empty:
        return pd.DataFrame([{
            "Batch No": batch_no,
            "Field": "All",
            "SC Value": "N/A",
            "Expected Value": "Not found in Packing List",
            "Validation": "❌"
        }])

    packing_row = packing_match.iloc[0]
    results = []
    
    def compare_field(field_name, sc_val, source_val):
        sc_val_clean = str(sc_val).strip().upper() if sc_val else ""
        source_val_clean = str(source_val).strip().upper() if source_val else ""
        if field_name == "Size":
            sc_val_clean = normalize_size(sc_val)
            source_val_clean = normalize_size(source_val)
        if field_name in ["Mfg. Date", "Exp. Date"]:
            sc_val_clean = normalize_date(sc_val)
            source_val_clean = normalize_date(source_val)
        if field_name == "Product Description":
            sc_val_clean = normalize_product_name(sc_val)
            source_val_clean = normalize_product_name(source_val)
        if sc_val_clean == source_val_clean:
            return {
                "Batch No": batch_no,
                "Field": field_name,
                "SC Value": sc_val,
                "Expected Value": source_val,
                "Validation": "✅"
            }
        else:
            return {
                "Batch No": batch_no,
                "Field": field_name,
                "SC Value": f"❌ {sc_val}",
                "Expected Value": f"✅ {source_val}",
                "Validation": "❌"
            }

    fields_to_check = [
        ("Size", sc_data.get("Size"), packing_row.get("Size")),
        ("Quantity", sc_data.get("Quantity"), packing_row.get("Qty")),
        ("Mfg. Date", sc_data.get("Mfg. Date"), packing_row.get("MFG Date")),
        ("Exp. Date", sc_data.get("Exp. Date"), packing_row.get("EXP Date")),
        ("Product Description", sc_data.get("Product Description"), packing_row.get("Description"))
    ]

    for field, sc_val, source_val in fields_to_check:
        results.append(compare_field(field, sc_val, source_val))

    return pd.DataFrame(results)
