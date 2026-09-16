#!/usr/bin/env python3
"""
Quick test to fetch PIDs from DDR Archive GraphQL
"""
import requests
import json

# Your 4 PIDs to test
TEST_PIDS = [
    "873981573030",
    "451248821104",
    "880612075513",
    "124881079617"
]

GRAPHQL_ENDPOINT = "https://api.ddrarchive.org/graphql"

# Query to fetch all media items with PIDs
query = """
query GetAllMediaItems {
  all_media_items {
    id
    pid
    title
    status
    copyright_holder
    public_uri
    pdf_files {
      role
      filename
      url
    }
    jpg_derivatives {
      role
      filename
      url
    }
  }
}
"""

def fetch_graphql():
    """Fetch from DDR Archive GraphQL"""
    try:
        response = requests.post(
            GRAPHQL_ENDPOINT,
            json={'query': query},
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ GraphQL request failed: {e}")
        return None

def check_pids(data):
    """Check if our test PIDs exist in the response"""
    if not data or 'data' not in data:
        print("❌ No data in response")
        return
    
    all_items = data['data'].get('all_media_items', [])
    print(f"\n📊 Total items from GraphQL: {len(all_items)}")
    
    # Extract all PIDs
    graphql_pids = {item.get('pid') for item in all_items if item.get('pid')}
    print(f"📊 Total PIDs in GraphQL: {len(graphql_pids)}")
    
    # Check our test PIDs
    print(f"\n🔍 Checking your 4 PIDs:")
    for pid in TEST_PIDS:
        found = pid in graphql_pids
        status = "✅ FOUND" if found else "❌ NOT FOUND"
        print(f"  {pid}: {status}")
    
    # Show which items match our PIDs
    print(f"\n📄 Matching items:")
    for item in all_items:
        pid = item.get('pid')
        if pid in TEST_PIDS:
            title = item.get('title', 'Untitled')
            has_pdf = len(item.get('pdf_files', [])) > 0
            has_jpg = len(item.get('jpg_derivatives', [])) > 0
            
            media_types = []
            if has_pdf: media_types.append('PDF')
            if has_jpg: media_types.append('JPG')
            
            training_eligible = has_pdf
            status = "✅ TRAINING ELIGIBLE" if training_eligible else "⚠️ JPG ONLY"
            
            print(f"\n  PID: {pid}")
            print(f"  Title: {title}")
            print(f"  Media: {', '.join(media_types)}")
            print(f"  Status: {status}")

if __name__ == "__main__":
    print("🔍 Fetching PIDs from DDR Archive GraphQL...")
    print(f"📡 Endpoint: {GRAPHQL_ENDPOINT}\n")
    
    data = fetch_graphql()
    
    if data:
        # Save full response for debugging
        with open('/tmp/graphql_full_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print(f"💾 Full response saved to /tmp/graphql_full_response.json")
        
        check_pids(data)
    else:
        print("❌ Failed to fetch data from GraphQL API")
