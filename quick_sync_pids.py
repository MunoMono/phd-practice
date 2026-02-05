"""
Quick script to sync parent PIDs using existing backend infrastructure
Run this INSIDE the backend container

PERMANENT ML GATE POLICIES (as of Feb 2026):
1. Only count PDF files with role='pdf_master' (excludes browser-friendly versions)
2. Match each master PDF to its digital asset by filename
3. Only count PDFs where the specific digital asset has use_for_ml=True
4. This ensures we only train on high-quality master PDFs that are explicitly approved

These policies ensure:
- No duplicate counting of master + browser versions
- Individual file-level ML approval (not just media item level)
- Only high-quality OCR-baked master PDFs for training
"""
import sys
sys.path.insert(0, '/app')

import requests
import json
from sqlalchemy import text
from app.core.database import LocalSessionLocal

GRAPHQL_ENDPOINT = "https://api.ddrarchive.org/graphql"

query = """
{
  records_v1(status: "published") {
    pid
    title
    project_start_date
    attached_media {
      pdf_files { role filename }
      digital_assets { use_for_ml filename }
    }
  }
}
"""

print("🔍 Fetching records from GraphQL...")
response = requests.post(GRAPHQL_ENDPOINT, json={'query': query}, timeout=30)
data = response.json()

records = data['data'].get('records_v1', [])
print(f"📊 Found {len(records)} parent records\n")

db = LocalSessionLocal()

for record in records:
    pid = record.get('pid')
    if not pid:
        continue
    
    title = record.get('title', 'Untitled')
    
    # PERMANENT ML GATE: Count MASTER PDF FILES with use_for_ml=TRUE
    # Policy enforced at individual file level (not media item level)
    # Only count pdf_master role files (not browser-friendly versions)
    # Match each PDF to its digital asset by filename and check ML flag individually
    pdf_count = 0
    for media in record.get('attached_media', []):
        # Get all PDF files with role=pdf_master (excludes browser versions)
        pdf_files = media.get('pdf_files', [])
        master_pdfs = [p for p in pdf_files if p.get('role') == 'pdf_master']
        
        # Create filename -> use_for_ml mapping from digital assets
        # This allows file-level ML approval granularity
        digital_assets = media.get('digital_assets', [])
        asset_ml_map = {}
        for asset in digital_assets:
            if isinstance(asset, dict):
                filename = asset.get('filename', '')
                use_for_ml = asset.get('use_for_ml', False)
                asset_ml_map[filename] = use_for_ml
        
        # Count only master PDFs that have use_for_ml=True at the individual file level
        for pdf in master_pdfs:
            pdf_filename = pdf.get('filename', '')
            if pdf_filename in asset_ml_map and asset_ml_map[pdf_filename]:
                pdf_count += 1
    
    year_str = record.get('project_start_date', '1970')
    year = int(year_str[:4]) if year_str and len(year_str) >= 4 else 1970
    
    metadata = {'pdf_count': pdf_count, 'synced_from': 'ddr_graphql'}
    
    # Check if exists
    result = db.execute(text("SELECT pid FROM documents WHERE pid = :pid"), {'pid': pid})
    exists = result.fetchone()
    
    if exists:
        db.execute(text("""
            UPDATE documents SET 
                title = :title,
                publication_year = :year,
                pdf_count = :pdf_count,
                doc_metadata = CAST(:metadata AS jsonb),
                last_synced_at = NOW()
            WHERE pid = :pid
        """), {
            'title': title, 'year': year, 'pdf_count': pdf_count,
            'metadata': json.dumps(metadata), 'pid': pid
        })
        print(f"✅ Updated: {pid} ({title})")
    else:
        db.execute(text("""
            INSERT INTO documents (
                document_id, title, publication_year, filename,
                pid, pdf_count, doc_metadata, last_synced_at
            ) VALUES (
                :doc_id, :title, :year, :filename,
                :pid, :pdf_count, CAST(:metadata AS jsonb), NOW()
            )
        """), {
            'doc_id': f"doc_pid_{pid}", 'title': title, 'year': year,
            'filename': f"{pid}.pdf", 'pid': pid, 'pdf_count': pdf_count,
            'metadata': json.dumps(metadata)
        })
        print(f"✅ Inserted: {pid} ({title})")
    
    db.commit()

# Verify
result = db.execute(text("SELECT pid, title, pdf_count FROM documents WHERE pid IS NOT NULL"))
rows = result.fetchall()
print(f"\n🔍 Database now has {len(rows)} PIDs:")
for row in rows:
    print(f"  • {row.pid}: {row.title} (PDFs: {row.pdf_count})")

db.close()
print("\n✅ Done!")
