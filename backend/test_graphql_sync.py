#!/usr/bin/env python3
"""
Test script for GraphQL-based PID sync

Tests the allowlist filter with real GraphQL data
"""
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.graphql_sync import GraphQLSyncService

# Your actual GraphQL response
SAMPLE_GRAPHQL_RESPONSE = {
  "all_media_items": [
    {
      "id": "87",
      "pid": "564310168393",
      "title": "Archer Systematic method for designers | 1963-4",
      "status": "published",
      "copyright_holder": "Copyright © Royal College of Art",
      "public_uri": "https://ddrarchive.org/id/record/564310168393",
      "jpg_derivatives": [
        {
          "role": "jpg_thumb",
          "url": "https://archive-media.lon1.digitaloceanspaces.com/ddr-archive/records/87/derivative/308e67089fda8f54fd8e9e0a4dba7e054208e78ad7c49052eaa3ee72773250b9__jpg_thumb__v1.jpg",
          "filename": "308e67089fda8f54fd8e9e0a4dba7e054208e78ad7c49052eaa3ee72773250b9.jpg",
          "label": "Archer Systematic method for designers | 1963-4"
        }
      ],
      "pdf_files": [
        {
          "role": "pdf_master",
          "url": "https://archive-media.lon1.digitaloceanspaces.com/ddr-archive/records/87/master/308e67089fda8f54fd8e9e0a4dba7e054208e78ad7c49052eaa3ee72773250b9__pdf_master__v1.pdf",
          "filename": "308e67089fda8f54fd8e9e0a4dba7e054208e78ad7c49052eaa3ee72773250b9.pdf",
          "label": "Archer Systematic method for designers | 1963-4"
        }
      ]
    },
    {
      "id": "97",
      "pid": "001808484369",
      "title": "Lower limb surgical plaster table | Job 73",
      "status": "published",
      "copyright_holder": "Copyright © Royal College of Art",
      "public_uri": "https://ddrarchive.org/id/record/001808484369",
      "jpg_derivatives": [
        {
          "role": "jpg_display",
          "url": "https://archive-media.lon1.digitaloceanspaces.com/ddr-archive/records/008832140000/derivative/0a6b5e5168454ec352092e7748ce3f45fcfd3bc16c6638820f3aa45935ee92ce__jpg_display__v1.jpg",
          "filename": "0a6b5e5168454ec352092e7748ce3f45fcfd3bc16c6638820f3aa45935ee92ce__jpg_display__v1.jpg",
          "label": "Couch with shin table in position"
        }
      ],
      "pdf_files": []
    },
    {
      "id": "85",
      "pid": "362524095549",
      "title": "Strathclyde Police console 146 2 | 1975",
      "status": "published",
      "copyright_holder": "Copyright © Royal College of Art",
      "public_uri": "https://ddrarchive.org/id/record/362524095549",
      "jpg_derivatives": [
        {
          "role": "jpg_thumb",
          "url": "https://archive-media.lon1.digitaloceanspaces.com/ddr-archive/records/362524095549/derivative/37f3fbe5a62400e5c59cc38bb4458157de6c0ff909d39b31e74ca5567b09c35c__jpg_thumb__v1.jpg",
          "filename": "37f3fbe5a62400e5c59cc38bb4458157de6c0ff909d39b31e74ca5567b09c35c__jpg_thumb__v1.jpg",
          "label": "Strathclyde Police console 146 2 | 1975.pdf"
        }
      ],
      "pdf_files": [
        {
          "role": "pdf_master",
          "url": "https://archive-media.lon1.digitaloceanspaces.com/ddr-archive/records/362524095549/master/37f3fbe5a62400e5c59cc38bb4458157de6c0ff909d39b31e74ca5567b09c35c__pdf_master__v1.pdf",
          "filename": "37f3fbe5a62400e5c59cc38bb4458157de6c0ff909d39b31e74ca5567b09c35c.pdf",
          "label": "Strathclyde Police console 146 2 | 1975.pdf"
        }
      ]
    }
  ]
}


def test_graphql_parsing():
    """Test parsing of GraphQL response"""
    print("=" * 80)
    print("TEST 1: Parsing GraphQL Response")
    print("=" * 80)
    
    sync = GraphQLSyncService()
    parsed = sync.parse_graphql_media_response(SAMPLE_GRAPHQL_RESPONSE)
    
    print(f"\n📊 Total items in GraphQL response: {parsed['total_items']}")
    print(f"✅ Training-eligible (PDFs): {parsed['training_eligible_count']}")
    print(f"📸 JPG-only (not eligible): {parsed['jpg_only_count']}")
    print(f"❌ No media: {parsed['no_media_count']}")
    
    print("\n" + "=" * 80)
    print("Training-Eligible Items (PDF or TIFF masters):")
    print("=" * 80)
    for item in parsed['training_eligible']:
        data = item['item']
        file_type = item['type']
        master_files = item.get('master_files', [])
        print(f"\n  PID: {data['pid']}")
        print(f"  Title: {data['title']}")
        print(f"  Type: {file_type.upper()}")
        print(f"  Master files: {len(master_files)}")
        if master_files:
            print(f"  URL: {master_files[0].get('url', 'N/A')}")
    
    print("\n" + "=" * 80)
    print("JPG-Only Items (Check DO Spaces for TIFF masters):")
    print("=" * 80)
    for item in parsed['jpg_only']:
        print(f"\n  PID: {item['pid']}")
        print(f"  Title: {item['title']}")
        print(f"  ⚠️  JPG derivatives present - TIFF masters should be in PID folder:")
        print(f"     ddr-archive/records/{item['pid']}/master/*.tif")
        print(f"  Action: Add 'tiff_files' array to GraphQL response for this record")
    
    return parsed


def test_dry_run_sync():
    """Test dry-run sync (doesn't actually insert to DB)"""
    print("\n\n" + "=" * 80)
    print("TEST 2: Dry-Run Sync (No Database Changes)")
    print("=" * 80)
    
    sync = GraphQLSyncService()
    result = sync.bulk_sync_from_graphql_response(
        SAMPLE_GRAPHQL_RESPONSE,
        dry_run=True
    )
    
    print(f"\n📊 Sync Statistics:")
    print(f"  Total items: {result['total_items']}")
    print(f"  Training-eligible: {result['training_eligible']}")
    print(f"  Would sync: {result['synced']}")
    print(f"  Would skip: {result['skipped']}")
    print(f"  Errors: {result['errors']}")
    print(f"  Dry run: {result['dry_run']}")
    
    return result


def test_allowlist_validation():
    """Test the allowlist filter logic"""
    print("\n\n" + "=" * 80)
    print("TEST 3: Allowlist Filter Validation")
    print("=" * 80)
    
    all_items = SAMPLE_GRAPHQL_RESPONSE['all_media_items']
    
    print("\n🔍 PID Allowlist Check:")
    print("-" * 80)
    
    allowed_pids = []
    needs_tiff_check = []
    
    for item in all_items:
        pid = item['pid']
        has_pdf = len(item.get('pdf_files', [])) > 0
        has_tiff = len(item.get('tiff_files', [])) > 0
        has_jpg = len(item.get('jpg_derivatives', [])) > 0
        
        if has_pdf or has_tiff:
            allowed_pids.append(pid)
            file_type = 'PDF' if has_pdf else 'TIFF'
            print(f"  ✅ PID {pid} - ALLOWED (has {file_type})")
        elif has_jpg:
            needs_tiff_check.append(pid)
            print(f"  ⚠️  PID {pid} - JPG derivatives only")
            print(f"     → Check DO Spaces for TIFF masters in ddr-archive/records/{pid}/master/")
        else:
            print(f"  ❌ PID {pid} - NO MEDIA")
    
    print(f"\n📋 Summary:")
    print(f"  Allowed PIDs (training corpus): {allowed_pids}")
    print(f"  Needs TIFF master check: {needs_tiff_check}")
    print(f"\n  ⚠️  NOTE: Items with JPG derivatives likely have TIFF masters in DO Spaces")
    print(f"     GraphQL response may need 'tiff_files' array populated")
    
    return {
        'allowed_pids': allowed_pids,
        'needs_tiff_check': needs_tiff_check
    }


def test_expected_s3_keys():
    """Show expected S3 keys that should be in training corpus"""
    print("\n\n" + "=" * 80)
    print("TEST 4: Expected S3 Keys for Training Corpus")
    print("=" * 80)
    
    print("\n🎯 These S3 objects should be ingested for training:")
    print("-" * 80)
    
    for item in SAMPLE_GRAPHQL_RESPONSE['all_media_items']:
        pid = item['pid']
        title = item['title']
        pdf_files = item.get('pdf_files', [])
        tiff_files = item.get('tiff_files', [])
        jpg_only = len(item.get('jpg_derivatives', [])) > 0
        
        if pdf_files:
            for pdf in pdf_files:
                print(f"\n  ✅ PDF MASTER")
                print(f"     PID: {pid}")
                print(f"     Title: {title}")
                print(f"     S3 Key: {pdf['url']}")
                print(f"     Filename: {pdf['filename']}")
        elif tiff_files:
            for tiff in tiff_files:
                print(f"\n  ✅ TIFF MASTER")
                print(f"     PID: {pid}")
                print(f"     Title: {title}")
                print(f"     S3 Key: {tiff['url']}")
                print(f"     Filename: {tiff['filename']}")
        elif jpg_only:
            print(f"\n  ⚠️  TIFF MASTERS EXPECTED (JPG derivatives present)")
            print(f"     PID: {pid}")
            print(f"     Title: {title}")
            print(f"     Expected path: ddr-archive/records/{pid}/master/*.tif")
            print(f"     → Add to GraphQL response as 'tiff_files' array")


if __name__ == "__main__":
    print("\n")
    print("🧪 " * 40)
    print("PID-Gated Training Corpus Filter - Test Suite")
    print("🧪 " * 40)
    
    # Run tests
    parsed = test_graphql_parsing()
    sync_result = test_dry_run_sync()
    allowlist = test_allowlist_validation()
    test_expected_s3_keys()
    
    # Final summary
    print("\n\n" + "=" * 80)
    print("✅ TEST SUMMARY")
    print("=" * 80)
    print(f"""
Your GraphQL response contains:
  • 3 total authority records with PIDs
  • Training-eligible assets:
    - PID 564310168393 (Archer) → PDF master ✅
    - PID 362524095549 (Strathclyde) → PDF master ✅
    - PID 001808484369 (Lower limb) → TIFF masters expected ⚠️
  
⚠️  ACTION REQUIRED for PID 001808484369:
   GraphQL response shows JPG derivatives but no TIFF masters.
   The TIFF masters should be in:
     ddr-archive/records/001808484369/master/*.tif
   
   Add 'tiff_files' array to GraphQL response to make this record training-eligible:
   {{
     "tiff_files": [
       {{
         "role": "tiff_master",
         "url": "https://archive-media.../master/[filename]__tiff_master__v1.tif",
         "filename": "[filename].tif",
         "label": "Lower limb surgical plaster table | Job 73"
       }}
     ]
   }}

✅ ALLOWLIST FILTER SUPPORTS BOTH PDFs AND TIFFs

With TIFFs included, ALL 3 records should be training-eligible.
Currently: 2 confirmed (PDFs), 1 needs TIFF metadata added to GraphQL.
    """)
    
    print("\n🎯 Next Steps:")
    print("  1. Run migration: psql -d epistemic_drift -f backend/migrations/001_add_pid_to_documents.sql")
    print("  2. Test actual sync: python -c 'from app.services.graphql_sync import GraphQLSyncService; ...'")
    print("  3. Query training corpus: SELECT pid, title FROM documents WHERE pid IS NOT NULL;")
