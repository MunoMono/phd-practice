#!/usr/bin/env python3
"""
Scheduled PID Authority Sync Script

Fetches all media items from DDR Archive GraphQL and syncs to database.
Designed to run as a cron job at 1am daily.
"""

import sys
import json
import urllib.request
from datetime import datetime


GRAPHQL_ENDPOINT = "https://api.ddrarchive.org/graphql"
SYNC_ENDPOINT = "http://localhost:8000/api/v1/sync/graphql"

# GraphQL query to fetch all records with digital assets and ML annotations
GRAPHQL_QUERY = """
query {
  records_v1(status: "published") {
    id
    pid
    title
    attached_media {
      id
      pid
      title
      used_for_ml
      ml_annotation
      digital_assets {
        role
        filename
        use_for_ml
        ml_pages
        ml_annotation
        mime
      }
    }
  }
}
"""


def fetch_from_graphql():
    """Fetch all media items from DDR Archive GraphQL API"""
    try:
        query_payload = {"query": GRAPHQL_QUERY}
        print(f"{datetime.now()} - Sending GraphQL query: {json.dumps(query_payload)[:500]}...")
        request_data = json.dumps(query_payload).encode()
        req = urllib.request.Request(
            GRAPHQL_ENDPOINT,
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        print(f"{datetime.now()} - Fetching from GraphQL API...")
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode())
            
            # Check for GraphQL errors
            if 'errors' in data:
                print(f"{datetime.now()} - GraphQL query errors:", file=sys.stderr)
                for error in data['errors']:
                    print(f"  - {error.get('message')}", file=sys.stderr)
                print(f"{datetime.now()} - Continuing with partial data...", file=sys.stderr)
            
            # Debug: log what we got
            if 'data' in data:
                print(f"{datetime.now()} - Data keys: {list(data['data'].keys() if data['data'] else [])}")
            
            print(f"{datetime.now()} - GraphQL fetch successful")
            return data
            
    except Exception as e:
        print(f"{datetime.now()} - GraphQL fetch failed: {e}", file=sys.stderr)
        sys.exit(1)


def sync_to_database(graphql_data):
    """Sync GraphQL data to local database"""
    try:
        # Debug: check what we're sending
        print(f"{datetime.now()} - GraphQL data keys before sync: {list(graphql_data.keys())}")
        if 'data' in graphql_data:
            print(f"{datetime.now()} - graphql_data['data'] is None: {graphql_data['data'] is None}")
        if 'errors' in graphql_data:
            print(f"{datetime.now()} - graphql_data has 'errors' key: {graphql_data['errors']}")
        
        payload = {
            "graphql_response": graphql_data
        }
        request_data = json.dumps(payload).encode()
        
        # dry_run=false as query parameter
        req = urllib.request.Request(
            f"{SYNC_ENDPOINT}?dry_run=false",
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        print(f"{datetime.now()} - Syncing to database...")
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode())
            print(f"{datetime.now()} - Sync complete: {json.dumps(result, indent=2)}")
            return result
            
    except Exception as e:
        print(f"{datetime.now()} - Database sync failed: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    print(f"{datetime.now()} - Starting scheduled PID authority sync")
    
    # Fetch from GraphQL
    graphql_data = fetch_from_graphql()
    
    # Sync to database
    result = sync_to_database(graphql_data)
    
    print(f"{datetime.now()} - Scheduled sync completed successfully")
    print(f"  - New PIDs: {result.get('new_count', 0)}")
    print(f"  - Updated PIDs: {result.get('updated_count', 0)}")
    print(f"  - Total processed: {result.get('total_count', 0)}")


if __name__ == "__main__":
    main()
