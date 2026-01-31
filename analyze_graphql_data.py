#!/usr/bin/env python3
import json
import glob

# Find the most recent GraphQL response file
files = glob.glob('/tmp/parent_pids_sync_*.json')
if not files:
    print("No GraphQL response files found")
    exit(1)

latest_file = max(files)
print(f"Analyzing: {latest_file}\n")

with open(latest_file) as f:
    data = json.load(f)

records = data['data']['records_v1']

for record in records:
    title = record.get('title', '')
    pid = record.get('pid')
    attached_media = record.get('attached_media', [])
    
    print(f"\n{'='*70}")
    print(f"PARENT: {title}")
    print(f"PID: {pid}")
    print(f"Attached Media Items: {len(attached_media)}")
    print(f"{'='*70}")
    
    total_pdfs_with_ml = 0
    total_pdfs_without_ml = 0
    
    for i, media in enumerate(attached_media, 1):
        media_pid = media.get('pid')
        media_title = media.get('title', 'Untitled')
        pdf_files = media.get('pdf_files', [])
        digital_assets = media.get('digital_assets', [])
        
        # Check ML flag
        has_ml_flag = False
        if isinstance(digital_assets, list):
            has_ml_flag = any(
                da.get('use_for_ml', False) 
                for da in digital_assets 
                if isinstance(da, dict)
            )
        elif isinstance(digital_assets, dict):
            has_ml_flag = digital_assets.get('use_for_ml', False)
        
        num_pdfs = len(pdf_files)
        
        if has_ml_flag:
            total_pdfs_with_ml += num_pdfs
        else:
            total_pdfs_without_ml += num_pdfs
        
        print(f"\n  Media Item {i}:")
        print(f"    PID: {media_pid}")
        print(f"    Title: {media_title[:50]}...")
        print(f"    PDF Files: {num_pdfs}")
        if pdf_files:
            for pdf in pdf_files:
                print(f"      - {pdf.get('filename')} (role: {pdf.get('role')})")
        print(f"    ML Flag (use_for_ml): {has_ml_flag}")
        if digital_assets:
            print(f"    Digital Assets: {len(digital_assets)}")
            for da in (digital_assets if isinstance(digital_assets, list) else [digital_assets]):
                if isinstance(da, dict):
                    print(f"      - use_for_ml={da.get('use_for_ml')}, annotation={da.get('ml_annotation')}")
    
    print(f"\n  📊 TOTALS for '{title}':")
    print(f"    PDFs with ML=TRUE: {total_pdfs_with_ml}")
    print(f"    PDFs with ML=FALSE/None: {total_pdfs_without_ml}")
    print(f"    Total PDFs: {total_pdfs_with_ml + total_pdfs_without_ml}")
