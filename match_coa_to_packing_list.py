import pandas as pd
import re
from datetime import datetime

#we have to give importance to the refernce code as ell for the size because th e size is dependent heavily on the reference codew ,
#reference code is unique for evvery products so even if we are hard coding the logic for sizes and product name it wont be a atter
def validate_against_packaging_list(coa_data: dict, packing_list_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns detailed validation of COA vs. Packing List for each field.
    """
    batch_no = str(coa_data.get("Batch No", "")).strip()
    matches = packing_list_df[packing_list_df["Batch No"].astype(str).str.strip() == batch_no]

    if matches.empty:
        return pd.DataFrame([{
            "Batch No": batch_no,
            "Field": "Batch No",
            "Expected Value": "Not found",
            "COA Value": batch_no,
            "Match": "❌"
        }])

    result_rows = []
    for _, row in matches.iterrows():
        checks = [
            ("Description", row.get("Description", ""), coa_data.get("Product Name", "")),
            ("Size", row.get("Size", ""), coa_data.get("Product Size", "")),
            ("MFG Date", normalize_date(row.get("MFG Date", "")), normalize_date(coa_data.get("Mfg. Date", ""))),
            ("EXP Date", normalize_date(row.get("EXP Date", "")), normalize_date(coa_data.get("Exp. Date", ""))),
            ("Quantity", str(row.get("Qty", row.get("Quantity", ""))).replace(",", ""), str(coa_data.get("Quantity Released") or coa_data.get("Shipping Qty") or "").replace(",", ""))
        ]

        for field, expected, actual in checks:
            if field == "Size":
                expected_norm = normalize_size(expected)
                actual_norm = normalize_size(actual)
            else:
                expected_norm = str(expected).strip().lower()
                actual_norm = str(actual).strip().lower()

            match = "✅" if expected_norm == actual_norm else "❌"

            result_rows.append({
                "Batch No": batch_no,
                "Field": field,
                "Expected Value": expected,
                "COA Value": actual,
                "Match": match
            })

    return pd.DataFrame(result_rows)


def compare(val1, val2):
    return "✅" if str(val1).strip().lower() == str(val2).strip().lower() else "❌"

def normalize_date(date_str):
    """
    Flexible date normalization: turns most human/short dates into YYYY-MM-DD or YYYY-MM, else returns as-is.
    """
    date_str = str(date_str).strip()
    if not date_str:
        return ""
    try:
        # Try to parse month/year, day optional
        dt = pd.to_datetime(date_str, errors='coerce')
        if pd.isna(dt):
            match = re.match(r"([A-Za-z]{3})[-\s,]?(\d{4})", date_str)
            if match:
                month = match.group(1).title()
                year = match.group(2)
                return f"{year}-{month}"
            else:
                return date_str
        return dt.strftime("%Y-%m-%d")
    except:
        return date_str

def normalize_size(size_str):
    """Standardizes size format to reduce case/spelling mismatches."""
    size_str = str(size_str).upper().strip()  # Make uppercase and strip
    size_str = re.sub(r'\s+', '', size_str)   # Remove all spaces
    size_str = size_str.replace("X", "x")     # Standardize separator
    size_str = size_str.replace("MM", "MM").replace("CM", "CM")  # Reinforce correct unit
    size_str = size_str.replace("G ", "G").replace("GAUGE", "G")
    size_str = size_str.replace("FR", "FR")  # for catheters
    return size_str


def normalize_product_name(text):
    """Cleans and flattens product names while preserving word tokens."""
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)  # allow spaces for splitting
    return re.sub(r"\s+", " ", text).strip()  # collapse multiple spaces

def description_match(description, product_name, product_size, product_type=None):
    def normalize_terms(text):
        text = str(text).lower().strip()
        text = text.replace("tip j", "jtip").replace("j-tip", "jtip")
        text = re.sub(r"[^a-z0-9\s]", "", text)
        return re.sub(r"\s+", " ", text).strip()

    desc_norm = normalize_terms(description)
    name_norm = normalize_terms(product_name)
    name_match = name_norm in desc_norm

    type_match = True
    if product_type:
        type_norm = normalize_terms(product_type)
        if type_norm and type_norm.strip():
            type_match = type_norm in desc_norm

    return "✅" if name_match and type_match else "❌"






def size_match(pack_size, coa_size, description):
    """
    Matches size field directly, OR confirms if size is present in description if packing list omits size.
    """
    # Normalize
    p_size = normalize_size(pack_size)
    c_size = normalize_size(coa_size)
    # Try direct match first
    if p_size and c_size:
        return "✅" if p_size == c_size else "❌"
    # If packing list has no size, check if size is embedded in description
    desc_norm = normalize_size(description)
    return "✅" if c_size and c_size in desc_norm else "❌"

def compare_quantity(pack_qty, coa_qty):
    try:
        return "✅" if int(str(pack_qty).replace(",","").strip()) == int(str(coa_qty).replace(",","").strip()) else "❌"
    except:
        return "❌"