import pdfplumber
import re

def parse_sterilization_certificate(uploaded_file):
    try:
        all_steri_data = []

        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if not page_text:
                    continue

                steri_data = {
                    "Batch No": None,
                    "Mfg. Date": None,
                    "Exp. Date": None,
                    "Product Description": None,
                    "Size": None,
                    "Quantity": None
                }

                # Extract fields from text
                patterns = {
                    "Batch No": r"Batch No[:\s]*([A-Z0-9/]+)",
                    "Mfg. Date": r"Mfg\. Date[:\s]*([A-Z]{3}\s*[-–]?\s*\d{4})",
                    "Exp. Date": r"Exp\. Date[:\s]*([A-Z]{3}\s*[-–]?\s*\d{4})",
                    "Product Description": r"Product Description[:\s]*(.+?)(?:\n|$)"
                }

                for key, pattern in patterns.items():
                    match = re.search(pattern, page_text, re.IGNORECASE | re.MULTILINE)
                    if match:
                        steri_data[key] = match.group(1).strip().upper()

                # Extract correct table for Size and Quantity
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    
                    header = table[0]
                    if header and any("Size" in str(cell) for cell in header):
                        # This is the correct table
                        for row in table[1:]:
                            if row and len(row) >= 4:
                                _, type_, size, quantity = row[:4]
                                if size and quantity:
                                    steri_data["Size"] = size.replace(" ", "").upper()
                                    steri_data["Quantity"] = quantity.strip()
                                    break  # Found, stop
                        break  # Found correct table, stop scanning

                all_steri_data.append(steri_data)

        return all_steri_data

    except Exception as e:
        print(f"❌ Sterilization Certificate Parsing Error: {e}")
        return None
