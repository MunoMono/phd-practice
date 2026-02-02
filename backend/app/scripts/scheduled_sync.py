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

# GraphQL query to fetch all media items with PIDs
GRAPHQL_QUERY = """
query {
  all_media_items {
    items {
      pid
      title
      authority_id
      media {
        format_type
        full_file_type
      }
    }
  }
}
"""


def fetch_from_graphql():
    """Fetch all media items from DDR Archive GraphQL API"""
    try:
        request_data = json.dumps({"query": GRAPHQL_QUERY}).encode()
        req = urllib.request.Request(
            GRAPHQL_ENDPOINT,
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        print(f"{datetime.now()} - Fetching from GraphQL API...")
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode())
            print(f"{datetime.now()} - GraphQL fetch successful")
            return data
            
    except Exception as e:
        print(f"{datetime.now()} - GraphQL fetch failed: {e}", file=sys.stderr)
        sys.exit(1)


def sync_to_database(graphql_data):
    """Sync GraphQL data to local database"""
    try:
        payload = {
            "graphql_response": graphql_data,
            "dry_run": False  # Actually perform the sync
        }
        request_data = json.dumps(payload).encode()
        
        req = urllib.request.Request(
            SYNC_ENDPOINT,
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
