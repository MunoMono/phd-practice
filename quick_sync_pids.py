"""
Quick script to sync parent PIDs using existing backend infrastructure
Run this INSIDE the backend container
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
      pdf_files { role }
      digital_assets { use_for_ml }
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
    
    # Count ACTUAL PDF FILES (not media items) where use_for_ml=TRUE
    pdf_count = 0
    for media in record.get('attached_media', []):
        # Check ML gate for this media item
        digital_assets = media.get('digital_assets', [])
        use_for_ml = any(asset.get('use_for_ml', False) for asset in digital_assets if isinstance(asset, dict))
        
        # If ML gate passed, count ACTUAL PDF files (not just media items)
        if use_for_ml:
            pdf_files = media.get('pdf_files', [])
            pdf_count += len(pdf_files)  # Count files, not items!
    
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
