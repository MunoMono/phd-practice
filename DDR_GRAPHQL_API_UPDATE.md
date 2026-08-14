# DDR Archive GraphQL API Update Required

## Overview
The testamentary traces system needs access to page-level ML annotation data from the DDR Archive GraphQL API. The UI already captures this data (`ml_pages` field visible in screenshots), but it's not exposed via the GraphQL API yet.

## Required Schema Changes

### Current ItemV1 Type
```graphql
type ItemV1 {
  id: ID!
  pid: String
  title: String
  caption: String
  used_for_ml: Boolean  # ✅ Already exposed
  
  # Media files
  pdf_files: [DigitalAsset]
  tiff_files: [DigitalAsset]
  jpg_derivatives: [DigitalAsset]
}
```

### Required Additions
```graphql
type ItemV1 {
  id: ID!
  pid: String
  title: String
  caption: String
  used_for_ml: Boolean  # ✅ Already exposed
  ml_pages: String      # ⚠️ NEEDS TO BE ADDED
  ml_annotation: String # ⚠️ NEEDS TO BE ADDED
  
  # Media files
  pdf_files: [DigitalAsset]
  tiff_files: [DigitalAsset]
  jpg_derivatives: [DigitalAsset]
}
```

### Also Update DigitalAsset Type
```graphql
type DigitalAsset {
  role: String
  key: String
  assetId: String
  filename: String
  mime: String
  use_for_ml: Boolean      # ⚠️ ADD (currently named 'used_for_ml' at item level)
  ml_pages: String         # ⚠️ ADD - page specifications
  ml_annotation: String    # ⚠️ ADD - annotation purpose
}
```

## Field Specifications

### ml_pages (String)
Free-form string supporting multiple patterns:

| Pattern | Description | Example |
|---------|-------------|---------|
| `""` | All pages | `""` |
| `"1-5"` | Pages 1 to 5 | `"1-5"` |
| `"1,3,5"` | Pages 1, 3, and 5 | `"1,3,5"` |
| `"all except 10-12"` | All except 10-12 | `"all except 10-12"` |
| `"2-"` | From page 2 onward | `"2-"` |

**Database Source**: This should map to the digital asset metadata field visible in the DDR Archive UI

### ml_annotation (String)
Purpose or description of the annotation. Examples:
- `"Training data for page layout analysis"`
- `"OCR ground truth"`
- `"Entity recognition training set"`

**Database Source**: This should map to the annotation field in the digital asset metadata

## Example Query After Update

```graphql
query {
  record_v1(id: "880612075513") {
    pid
    title
    attached_media {
      id
      title
      used_for_ml
      ml_pages
      ml_annotation
      pdf_files {
        filename
        use_for_ml
        ml_pages
        ml_annotation
      }
    }
  }
}
```

## Expected Response
```json
{
  "data": {
    "record_v1": {
      "pid": "880612075513",
      "title": "RCA Prospectuses | 1967-85",
      "attached_media": [
        {
          "id": "abc123",
          "title": "RCA Prospectus 1967",
          "used_for_ml": true,
          "ml_pages": "1-82",
          "ml_annotation": "Full document for ML training",
          "pdf_files": [
            {
              "filename": "rca_prospectus_1967.pdf",
              "use_for_ml": true,
              "ml_pages": "1-82",
              "ml_annotation": "Full document for ML training"
            }
          ]
        },
        {
          "id": "def456",
          "title": "RCA Prospectus 1968",
          "used_for_ml": false,
          "ml_pages": "",
          "ml_annotation": "",
          "pdf_files": [
            {
              "filename": "rca_prospectus_1968.pdf",
              "use_for_ml": false,
              "ml_pages": "",
              "ml_annotation": ""
            }
          ]
        }
      ]
    }
  }
}
```

## Implementation Notes

### Database Mapping
The DDR Archive ingestion platform already stores these fields in the digital asset metadata:
- `use_for_ml` - Boolean toggle (visible in UI)
- `ml_pages` - String field (visible in UI showing "82", "80", "68", etc.)
- `ml_annotation` - Text field for annotation purpose

### Resolver Implementation
The GraphQL resolvers need to:
1. Access the digital asset metadata table
2. Extract `ml_pages` and `ml_annotation` fields
3. Return them alongside existing fields

### Backwards Compatibility
- All new fields should be nullable/optional
- Existing queries will continue to work
- Clients can gradually adopt the new fields

## Testing After Implementation

Once deployed, test with:
```bash
curl -X POST https://api.ddrarchive.org/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { record_v1(id: \"880612075513\") { pid title attached_media { id used_for_ml ml_pages ml_annotation pdf_files { filename use_for_ml ml_pages } } } }"
  }' | python3 -m json.tool
```

## Impact on Testamentary Traces System

Once these fields are exposed:
1. ✅ Scheduled sync will automatically capture them (code already updated)
2. ✅ `authority_data` JSONB field will store the complete metadata
3. ✅ API endpoint `/api/v1/documents/{id}/ml-annotations` is ready
4. ✅ ML processing pipeline can parse page specifications
5. ✅ Frontend can display accurate ML training corpus statistics

## Priority
**HIGH** - This blocks accurate ML training corpus management and page-level annotation tracking.
