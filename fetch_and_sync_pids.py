#!/usr/bin/env python3
"""
Fetch PIDs from DDR Archive GraphQL and sync to droplet database
"""
import requests
import json

GRAPHQL_ENDPOINT = "https://api.ddrarchive.org/graphql"

# Query for parent authority records with attached media
query = """
{
  records_v1(status: "published") {
    id
    pid
    title
    status
    level
    reference_code
    scope_and_content
    date_begin
    date_end
    
    # DDR metadata
    ddr_period
    project_theme
    methodology
    epistemic_stance
    
    # Project details
    project_title
    project_job_number
    project_start_date
    project_end_date
    
    # Rights
    copyright_holder
    rights_holders
    
    # All attached media for this parent
    attached_media {
      id
      pid
      title
      caption
      attachment_role
      attachment_sequence
      
      # Image files
      jpg_derivatives {
        role
        url
        signed_url
        filename
        label
      }
      
      # PDF files
      pdf_files {
        role
        url
        signed_url
        filename
        label
      }
      
      # ML fields
      digital_assets {
        use_for_ml
        ml_annotation
      }
    }
  }
}
"""

def fetch_records():
    """Fetch parent records from DDR Archive GraphQL"""
    print("🔍 Fetching records from DDR Archive GraphQL...")
    print(f"📡 Endpoint: {GRAPHQL_ENDPOINT}\n")
    
    try:
        response = requests.post(
            GRAPHQL_ENDPOINT,
            json={'query': query},
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        # Save response
        with open('/tmp/records_v1_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print(f"💾 Response saved to /tmp/records_v1_response.json\n")
        
        return data
        
    except Exception as e:
        print(f"❌ GraphQL request failed: {e}")
        return None

def analyze_records(data):
    """Analyze the records and return parent PIDs with metadata"""
    if not data or 'data' not in data:
        print("❌ No data in response")
        if data and 'errors' in data:
            print(f"GraphQL Errors: {data['errors']}")
        return []
    
    records = data['data'].get('records_v1', [])
    print(f"📊 Total parent records: {len(records)}\n")
    
    parent_records = []
    
    for record in records:
        pid = record.get('pid')
        title = record.get('title', 'Untitled')
        attached_media = record.get('attached_media', [])
        
        # Count PDFs with ML TRUE flag
        pdf_count = 0
        for media in attached_media:
            has_pdf = bool(media.get('pdf_files'))
            digital_assets = media.get('digital_assets', [])
            # digital_assets is a list, check if any have use_for_ml=True
            use_for_ml = False
            if isinstance(digital_assets, list):
                use_for_ml = any(asset.get('use_for_ml', False) for asset in digital_assets if isinstance(asset, dict))
            elif isinstance(digital_assets, dict):
                use_for_ml = digital_assets.get('use_for_ml', False)
            
            if has_pdf and use_for_ml:
                pdf_count += 1
        
        # Count all JPGs
        jpg_count = sum(1 for m in attached_media if m.get('jpg_derivatives'))
        
        # Collect child PIDs
        child_pids = [m.get('pid') for m in attached_media if m.get('pid')]
        
        print(f"📄 PID: {pid}")
        print(f"   Title: {title}")
        print(f"   Attached Media: {len(attached_media)} items")
        print(f"   - PDFs (ML=TRUE): {pdf_count}")
        print(f"   - JPGs: {jpg_count}")
        if child_pids:
            print(f"   - Child PIDs: {child_pids}")
        print()
        
        if pid:
            parent_records.append({
                'pid': pid,
                'title': title,
                'pdf_count': pdf_count,
                'year': record.get('project_start_date', '1970')[:4] if record.get('project_start_date') else '1970'
            })
    
    return parent_records

def insert_pids_to_droplet(parent_records):
    """Insert parent PIDs with metadata to droplet database"""
    print(f"\n📝 Inserting {len(parent_records)} parent PIDs to droplet database...")
    
    for record in parent_records:
        pid = record['pid']
        title = record['title'].replace("'", "''")  # Escape single quotes
        pdf_count = record['pdf_count']
        year = record['year']
        
        # Create a document record with this PID and metadata
        # Use double quotes in JSON, escape them for shell
        json_str = json.dumps({"pdf_count": pdf_count})
        insert_sql = f"""
        INSERT INTO documents (document_id, title, publication_year, filename, pid, pdf_count, doc_metadata)
        VALUES (
            'doc_pid_{pid}',
            '{title}',
            {year},
            '{pid}.pdf',
            '{pid}',
            {pdf_count},
            '{json_str}'::jsonb
        )
        ON CONFLICT (pid) DO UPDATE SET
            title = EXCLUDED.title,
            publication_year = EXCLUDED.publication_year,
            pdf_count = EXCLUDED.pdf_count,
            doc_metadata = EXCLUDED.doc_metadata;
        """
        
        cmd = f'ssh root@104.248.170.26 "docker exec epistemic-drift-db psql -U postgres -d epistemic_drift -c \\"{insert_sql}\\""'
        print(f"  Inserting PID: {pid} ({title})")
        print(f"    PDF count (ML=TRUE): {pdf_count}")
        import subprocess
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    ⚠️  Error: {result.stderr}")
        else:
            print(f"    ✅ Inserted")
    
    print("\n✅ Done!")

if __name__ == "__main__":
    # Fetch records
    data = fetch_records()
    
    if data:
        # Analyze and get parent records with metadata
        parent_records = analyze_records(data)
        
        if parent_records:
            print(f"\n🎯 Found {len(parent_records)} parent PIDs to sync")
            
            # Insert to droplet
            insert_pids_to_droplet(parent_records)
            
            # Verify
            print("\n🔍 Verifying database...")
            import subprocess
            result = subprocess.run(
                'ssh root@104.248.170.26 "docker exec epistemic-drift-db psql -U postgres -d epistemic_drift -c \\"SELECT pid, title FROM documents WHERE pid IS NOT NULL ORDER BY pid;\\""',
                shell=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)
        else:
            print("❌ No parent PIDs found")
