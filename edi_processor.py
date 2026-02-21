import json
import collections
import collections.abc
collections.Iterable = collections.abc.Iterable
from badx12 import Parser

def process_edi_file(edi_content):
    """
    Parses EDI content while maintaining segment sequence and removing raw text.
    Handles both 'Wrapped' (continuous) and 'Unwrapped' (newline-formatted) files.
    """
    
    # --- SANITIZATION STEP ---
    # EDI files often come with newlines for readability (unwrapped).
    # We must remove these if they are not the actual segment terminators
    # to ensure the parser sees a continuous stream (wrapped).
    if edi_content and len(edi_content) > 106:
        # The ISA segment is fixed-length. The segment terminator is at index 105.
        # (ISA is 106 chars long, 0-indexed position 105 is the terminator)
        potential_terminator = edi_content[105]
        
        # If the terminator is NOT a newline character, it means newlines are just 
        # formatting garbage. We strip them to normalize the input.
        if potential_terminator not in ['\r', '\n']:
            edi_content = edi_content.replace('\n', '').replace('\r', '')

    parser = Parser()
    document = parser.parse_document(edi_content)
    
    # 1. Use the reliable to_dict() method as a base
    full_data = document.to_dict()
    
    # 2. Extract configuration and remove raw 'text'
    doc_structure = full_data.get('document', {})
    config = doc_structure.get('config', {})
    interchange = doc_structure.get('interchange', {})
    
    sequential_segments = []

    def format_segment(seg_name, fields_list):
        """Helper to format fields as objects: {"name": "TAG01", "content": "VAL"}"""
        formatted = []
        for i, field in enumerate(fields_list, 1):
            formatted.append({
                "name": f"{seg_name}{str(i).zfill(2)}",
                "content": field.get('content', '')
            })
        return {"segment": seg_name, "fields": formatted}

    # 3. Manually reconstruct the sequence from the dictionary hierarchy
    # Add Interchange Header
    if 'header' in interchange:
        sequential_segments.append(format_segment('ISA', interchange['header'].get('fields', [])))

    for group in interchange.get('groups', []):
        # Add Group Header
        if 'header' in group:
            sequential_segments.append(format_segment('GS', group['header'].get('fields', [])))
        
        for txn in group.get('transaction_sets', []):
            # Add Transaction Header
            if 'header' in txn:
                sequential_segments.append(format_segment('ST', txn['header'].get('fields', [])))
            
            # Add Transaction Body Segments (BIG, IT1, PID, etc.) in order
            for body_seg in txn.get('body', []):
                seg_name = body_seg.get('fields', [{}])[0].get('content', 'UNKNOWN')
                # Skip the segment name itself from the fields list
                fields = body_seg.get('fields', [])[1:]
                sequential_segments.append(format_segment(seg_name, fields))
            
            # Add Transaction Trailer
            if 'trailer' in txn:
                sequential_segments.append(format_segment('SE', txn['trailer'].get('fields', [])))
        
        # Add Group Trailer
        if 'trailer' in group:
            sequential_segments.append(format_segment('GE', group['trailer'].get('fields', [])))

    # Add Interchange Trailer
    if 'trailer' in interchange:
        sequential_segments.append(format_segment('IEA', interchange['trailer'].get('fields', [])))

    # 4. Construct final JSON result
    json_data = {
        "document": {
            "config": config,
            "segments": sequential_segments
        }
    }
    
    # 5. Extract 810 Invoice Summaries for Sheets
    transactions = []
    try:
        # Check if groups exist, otherwise handle empty gracefully
        groups = interchange.get('groups', [])
        if not groups:
            transactions.append(["Warning", "No Groups Found (Check File Format)"])
            
        for group in groups:
            for txn in group.get('transaction_sets', []):
                header_fields = txn.get('header', {}).get('fields', [])
                # ST02 is the second field
                txn_id = header_fields[1].get('content', 'Unknown') if len(header_fields) > 1 else "Unknown"
                transactions.append([txn_id, "Processed"])
    except Exception as e:
        transactions.append(["Error", f"Extraction failed: {str(e)}"])

    return json_data, transactions