# Data intake policy

Every source record must answer:

- What is the source?
- Which exact edition or release was used?
- Who owns or licenses it?
- May it be copied, modified, indexed, displayed, and redistributed?
- What attribution is required?
- What checksum/version identifies the imported data?
- Has a qualified reviewer checked the content policy?

## Record schema

```json
{
  "id": "quran:2:255",
  "type": "quran",
  "collection": "Quran",
  "reference": "Al-Baqarah 2:255",
  "text_ar": "...",
  "source_id": "tanzil-quran-text",
  "edition": "...",
  "checksum": "sha256:...",
  "license": "...",
  "license_url": "...",
  "review_status": "approved-candidate"
}
```

Keep canonical text and normalized search text in separate fields. Never silently edit a canonical quotation.
