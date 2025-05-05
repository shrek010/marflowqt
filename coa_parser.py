import pdfplumber
import re

def parse_certificate_of_analysis(uploaded_file):
    try:
        coa_data = {
            "Product Name": None,
            "Product Type": None,
            "Batch No": None,
            "Product Size": None,
            "Mfg. Date": None,
            "Exp. Date": None,
            "Shipping Qty": None,
            "Quantity Released": None
        }

        with pdfplumber.open(uploaded_file) as pdf:
            full_text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

        # Define patterns
        patterns = {
            "Product Name": r"Product Name\s+(.*?)\s+Certificate No",
            "Batch No": r"Batch No\.\s+(.*?)\s+(?:Product Type|Product Size|Certificate No)",
            "Product Size": r"Product Size\s+([A-Z0-9 ,.+\-xXcmCM]+)",
            "Mfg. Date": r"Mfg\. Date\s+(.*?)\s+Product Size",
            "Exp. Date": r"Exp\. Date\s+(.*?)\s+Actual Batch Size",
            "Shipping Qty": r"Shipping Qty\.\s+(\d+)",
            "Quantity Released": r"Quantity Released\s+(\d+)"
        }

        # First: handle Product Type manually so it’s strict
        lines = full_text.splitlines()
        for i, line in enumerate(lines):
            if "product type" in line.lower():
                match = re.search(r"Product Type\s*[:\-]?\s*(.*)", line, re.IGNORECASE)
                if match:
                    val = match.group(1).strip()
                    if val and not re.search(r"^(PRODUCT SIZE|CERTIFICATE|BATCH|DATE|QTY)", val, re.IGNORECASE):
                        val = val.upper().replace("X", "x").replace("CH ", "CH").replace("CM", "cm")
                        val = re.sub(r"\s+", " ", val)
                        coa_data["Product Type"] = val
                        print(f"✅ Matched Product Type: {val}")
                        break  # Only take first valid match

        # Then: extract the rest normally
        for key, pattern in patterns.items():
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                value = value.upper().replace("X", "x").replace("CH ", "CH").replace("CM", "cm")
                value = re.sub(r"\s+", " ", value)
                coa_data[key] = value
                print(f"✅ Matched {key}: {value}")

        return coa_data

    except Exception as e:
        print(f"❌ CA Parsing Error: {e}")
        return None
