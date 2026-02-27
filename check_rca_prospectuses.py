#!/usr/bin/env python3
"""Check RCA Prospectuses PID 880612075513 media items"""
import requests
import json

query = """
{
  records_v1(status: "published") {
    pid
    title
    attached_media {
      pdf_files { role filename }
      digital_assets { use_for_ml filename }
    }
  }
}
"""

response = requests.post("https://api.ddrarchive.org/graphql", json={'query': query}, timeout=30)

try:
    data = response.json()
except Exception as e:
    print(f"Error parsing response: {e}")
    print(f"Response text: {response.text[:500]}")
    exit(1)

if not data or 'data' not in data or data['data'] is None:
    print(f"Error in response: {data}")
    exit(1)

records = data['data']['records_v1']
for r in records:
    if r['pid'] == '880612075513':
        print(f"PID: {r['pid']}")
        print(f"Title: {r['title']}")
        print(f"\nTotal media items: {len(r.get('attached_media', []))}")
        
        total_pdfs_with_ml = 0
        total_pdfs_without_ml = 0
        
        for idx, media in enumerate(r.get('attached_media', []), 1):
            assets = media.get('digital_assets', [])
            pdf_files = media.get('pdf_files', [])
            
            # Check if ANY asset in this media item has use_for_ml=True
            use_for_ml = any(a.get('use_for_ml', False) for a in assets if isinstance(a, dict))
            
            print(f"\nMedia item {idx}:")
            print(f"  PDF files: {len(pdf_files)}")
            print(f"  use_for_ml (any): {use_for_ml}")
            
            # Count master PDFs only
            master_pdfs = [p for p in pdf_files if p.get('role') == 'pdf_master']
            print(f"  Master PDFs (role=pdf_master): {len(master_pdfs)}")
            
            # Create a map of filename -> use_for_ml from digital_assets
            asset_ml_map = {}
            for asset in assets:
                if isinstance(asset, dict):
                    fname = asset.get('filename', '')
                    ml_flag = asset.get('use_for_ml', False)
                    asset_ml_map[fname] = ml_flag
            
            # Count master PDFs that have use_for_ml=True
            ml_enabled_masters = 0
            ml_disabled_masters = 0
            for pdf in master_pdfs:
                pdf_filename = pdf.get('filename', '')
                if pdf_filename in asset_ml_map and asset_ml_map[pdf_filename]:
                    ml_enabled_masters += 1
                else:
                    ml_disabled_masters += 1
                    if pdf_filename in asset_ml_map and not asset_ml_map[pdf_filename]:
                        print(f"    ⚠️  Master PDF with ML=False: {pdf_filename[:60]}")
            
            print(f"  Master PDFs with ML=True: {ml_enabled_masters}")
            print(f"  Master PDFs with ML=False: {ml_disabled_masters}")
            
            total_pdfs_with_ml += ml_enabled_masters
            total_pdfs_without_ml += ml_disabled_masters
        
        print(f"\n=== SUMMARY ===")
        print(f"Total PDFs with use_for_ml=True:  {total_pdfs_with_ml}")
        print(f"Total PDFs with use_for_ml=False: {total_pdfs_without_ml}")
        print(f"TOTAL PDFs: {total_pdfs_with_ml + total_pdfs_without_ml}")
        break
