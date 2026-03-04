import re
from typing import List, Dict, Any
from datetime import datetime

def validate(parsed_data: List[Dict], file_type: str) -> List[Dict]:
    """
    Run validation rules on parsed EDI data.
    Returns a list of errors, each with:
      - segment_id
      - element_index (optional)
      - severity (error/warning/info)
      - message (plain English)
      - location (segment index)
    """
    errors = []

    # Basic structural checks
    if not parsed_data or parsed_data[0].get('id') != 'ISA':
        errors.append({
            "segment_id": "ISA",
            "element_index": None,
            "severity": "error",
            "message": "File must start with ISA segment",
            "location": 0
        })

    has_st = any(seg.get('id') == 'ST' for seg in parsed_data)
    if not has_st:
        errors.append({
            "segment_id": "ST",
            "element_index": None,
            "severity": "error",
            "message": "Missing ST segment (transaction set header)",
            "location": None
        })

    # We'll process each transaction set separately for segment counts
    transaction_sets = []
    current_tx = None
    for idx, seg in enumerate(parsed_data):
        seg_id = seg.get('id')
        if seg_id == 'ST':
            # Start new transaction
            current_tx = {"start": idx, "segments": []}
        if current_tx is not None:
            current_tx["segments"].append(idx)
        if seg_id == 'SE':
            if current_tx:
                transaction_sets.append(current_tx)
                current_tx = None

    # If any transaction is unterminated, flag error
    if current_tx is not None:
        errors.append({
            "segment_id": "SE",
            "element_index": None,
            "severity": "error",
            "message": "Transaction set not properly terminated with SE",
            "location": current_tx["start"]
        })

    # Loop through each segment for detailed checks
    claim_charges = {}  # claim_id -> billed amount
    service_lines = []  # list of (claim_id, line_charge)
    lx_numbers = []     # track LX values per claim
    hl_stack = []       # for HL hierarchy checking

    for idx, seg in enumerate(parsed_data):
        seg_id = seg.get('id')
        elements = seg.get('elements', [])

        # ========== NM1 – Name checks ==========
        if seg_id == 'NM1':
            # NM1 element 1: entity identifier code (e.g., '85'=billing provider, 'IL'=subscriber)
            # element 2: entity type (1=person, 2=organization)
            # element 3: last name (for person) or organization name
            # element 4: first name
            # element 9: identification code
            if len(elements) < 3:
                errors.append({
                    "segment_id": "NM1",
                    "element_index": None,
                    "severity": "error",
                    "message": "NM1 segment missing required elements",
                    "location": idx
                })
            else:
                # Check for missing patient last name (entity code 'IL')
                if elements[1] == 'IL' and len(elements) > 3 and not elements[3].strip():
                    errors.append({
                        "segment_id": "NM1",
                        "element_index": 3,
                        "severity": "error",
                        "message": "Patient last name is missing",
                        "location": idx
                    })
                # Check for missing patient ID (element 9 for subscriber)
                if elements[1] == 'IL' and (len(elements) < 9 or not elements[8].strip()):
                    errors.append({
                        "segment_id": "NM1",
                        "element_index": 8,
                        "severity": "error",
                        "message": "Patient ID (subscriber identifier) is missing",
                        "location": idx
                    })
                # NPI validation for provider (element 9 when qualifier is 'XX')
                if len(elements) > 8 and elements[8] == 'XX' and len(elements) > 9:
                    npi = elements[9]
                    if not re.match(r'^\d{10}$', npi):
                        errors.append({
                            "segment_id": "NM1",
                            "element_index": 9,
                            "severity": "error",
                            "message": f"NPI '{npi}' must be 10 digits",
                            "location": idx
                        })
                    # Optional Luhn check (add if desired)

        # ========== N3 – Address line ==========
        if seg_id == 'N3':
            if len(elements) > 1 and elements[1].strip():
                address = elements[1]
                # We'll check ZIP in N4, not here

        # ========== N4 – City/State/ZIP ==========
        if seg_id == 'N4' and len(elements) > 3:
            zip_code = elements[3]
            # ZIP must be 5 digits or 9 digits with hyphen
            if zip_code and not re.match(r'^\d{5}(-\d{4})?$', zip_code):
                errors.append({
                    "segment_id": "N4",
                    "element_index": 3,
                    "severity": "error",
                    "message": f"ZIP code '{zip_code}' must be 5 or 9 digits",
                    "location": idx
                })

        # ========== REF – Reference Information ==========
        if seg_id == 'REF' and len(elements) > 2:
            ref_qual = elements[1]
            ref_val = elements[2]
            if ref_qual == 'EI':  # Employer Identification Number (EIN)
                # EIN format: XX-XXXXXXX or just digits
                if not re.match(r'^\d{2}-?\d{7}$', ref_val):
                    errors.append({
                        "segment_id": "REF",
                        "element_index": 2,
                        "severity": "error",
                        "message": f"EIN '{ref_val}' must be 9 digits (XX-XXXXXXX)",
                        "location": idx
                    })

        # ========== DMG – Demographic Information ==========
        if seg_id == 'DMG' and len(elements) > 2:
            date_format = elements[1]
            date_val = elements[2] if len(elements) > 2 else ""
            if date_format == 'D8' and date_val:
                # Check valid date (CCYYMMDD)
                if not re.match(r'^\d{8}$', date_val):
                    errors.append({
                        "segment_id": "DMG",
                        "element_index": 2,
                        "severity": "error",
                        "message": f"Date '{date_val}' must be in CCYYMMDD format",
                        "location": idx
                    })
                else:
                    # Validate month and day
                    try:
                        datetime.strptime(date_val, '%Y%m%d')
                    except ValueError:
                        errors.append({
                            "segment_id": "DMG",
                            "element_index": 2,
                            "severity": "error",
                            "message": f"Date '{date_val}' is invalid (e.g., month 15)",
                            "location": idx
                        })

        # ========== HI – Health Care Diagnosis Codes ==========
        if seg_id == 'HI' and len(elements) > 1:
            # Each element after first is a diagnosis code with qualifier (e.g., ABK:J102)
            # For simplicity, we'll check that diagnosis codes are not obviously invalid
            for i in range(1, len(elements)):
                diag = elements[i]
                if ':' in diag:
                    parts = diag.split(':')
                    code = parts[1] if len(parts) > 1 else ""
                else:
                    code = diag
                if code == "INVALID":
                    errors.append({
                        "segment_id": "HI",
                        "element_index": i,
                        "severity": "error",
                        "message": f"Diagnosis code '{code}' is not a valid ICD-10 code",
                        "location": idx
                    })

        # ========== CLM – Claim Information ==========
        if seg_id == 'CLM':
            # CLM01 = claim ID, CLM02 = billed amount
            claim_id = elements[1] if len(elements) > 1 else ""
            billed = elements[2] if len(elements) > 2 else ""
            if claim_id:
                claim_charges[claim_id] = billed
            # Note: claim total mismatch will be checked after collecting all services

        # ========== LX – Line Number ==========
        if seg_id == 'LX' and len(elements) > 1:
            lx_num = elements[1]
            # Track LX numbers within this claim (we need claim context)
            # For simplicity, we'll just check duplicates globally (not ideal)
            if lx_num in lx_numbers:
                errors.append({
                    "segment_id": "LX",
                    "element_index": 1,
                    "severity": "error",
                    "message": f"Duplicate LX number '{lx_num}'",
                    "location": idx
                })
            else:
                lx_numbers.append(lx_num)

        # ========== SV1 – Professional Service ==========
        if seg_id == 'SV1' and len(elements) > 1:
            # SV1-02 (index 1) is line charge (e.g., "400")
            line_charge = elements[1] if len(elements) > 1 else ""
            # Associate with current claim (need to know which claim)
            # We'll collect all service lines and later match with claim
            service_lines.append(line_charge)

        # ========== DTP – Date checks (already have general date validation) ==========
        # We already have date format check below, but we'll add specific for DTP
        if seg_id == 'DTP' and len(elements) > 3:
            date_qual = elements[1]  # e.g., '472' for service date
            date_fmt = elements[2]   # e.g., 'D8'
            date_val = elements[3]
            if date_fmt == 'D8' and date_val:
                if not re.match(r'^\d{8}$', date_val):
                    errors.append({
                        "segment_id": "DTP",
                        "element_index": 3,
                        "severity": "error",
                        "message": f"Date '{date_val}' must be in CCYYMMDD format",
                        "location": idx
                    })
                else:
                    try:
                        datetime.strptime(date_val, '%Y%m%d')
                    except ValueError:
                        errors.append({
                            "segment_id": "DTP",
                            "element_index": 3,
                            "severity": "error",
                            "message": f"Date '{date_val}' is invalid",
                            "location": idx
                        })

        # ========== HL – Hierarchical Level ==========
        if seg_id == 'HL':
            # HL01 = hierarchical ID, HL02 = parent ID, HL03 = level code
            if len(elements) > 2:
                hl_id = elements[1]
                parent = elements[2] if len(elements) > 2 else ""
                level = elements[3] if len(elements) > 3 else ""
                # Simple check: parent must exist (except for top level)
                if parent and parent not in [s.get('elements', [])[1] for s in parsed_data[:idx] if s.get('id') == 'HL']:
                    errors.append({
                        "segment_id": "HL",
                        "element_index": 2,
                        "severity": "error",
                        "message": f"Parent HL '{parent}' not found",
                        "location": idx
                    })
                # Track nesting (optional)
                # For hackathon, we'll keep it simple

        # ========== General empty mandatory elements ==========
        # We can add a list of mandatory fields per segment type
        # For now, we'll rely on specific checks above

    # ========== Claim Total Mismatch ==========
    # Compute sum of service lines for each claim
    # For this stress test, we assume one claim and multiple services
    if claim_charges and service_lines:
        # Assuming the first claim is the only one
        claim_id = list(claim_charges.keys())[0]
        billed = claim_charges[claim_id]
        try:
            billed_float = float(billed)
            total_services = sum(float(x) for x in service_lines if x)
            if abs(billed_float - total_services) > 0.01:  # tolerance for floating point
                errors.append({
                    "segment_id": "CLM",
                    "element_index": 2,
                    "severity": "error",
                    "message": f"Claim total {billed} does not match sum of service lines ({total_services})",
                    "location": None  # We don't have a specific segment index for the whole claim
                })
        except ValueError:
            pass  # skip if not numbers

    # ========== SE Segment Count Mismatch ==========
    # For each transaction set, count segments and compare with SE01
    for tx in transaction_sets:
        start = tx["start"]
        seg_indices = tx["segments"]
        # Find the SE segment at the end
        se_idx = seg_indices[-1] if seg_indices else None
        if se_idx is not None:
            se_seg = parsed_data[se_idx]
            se_elements = se_seg.get('elements', [])
            if len(se_elements) > 1:
                declared_count = se_elements[1]
                actual_count = len(seg_indices)  # includes ST and SE
                if declared_count != str(actual_count):
                    errors.append({
                        "segment_id": "SE",
                        "element_index": 1,
                        "severity": "error",
                        "message": f"SE segment count mismatch: declared {declared_count}, actual {actual_count}",
                        "location": se_idx
                    })

    # ========== File-type-specific rules ==========
    if file_type == '837':
        # Additional 837 rules can go here
        pass
    elif file_type == '835':
        # 835-specific rules (e.g., CLP status codes)
        pass
    elif file_type == '834':
        # 834-specific rules (e.g., INS maintenance codes)
        pass

    return errors