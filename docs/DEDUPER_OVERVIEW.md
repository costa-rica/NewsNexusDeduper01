# NewsNexusDeduper01: Project Overview

## Project Folder Structure

```
NewsNexusDeduper01/
├── docs/
│   └── DEDUPER_OVERVIEW.md      # project overview documentation
├── requirements.txt             # dependencies
├── README.md
└── src/
    ├── main.py                  # CLI entry point with subcommands
    ├── config.py                # environment and config values
    ├── db.py                    # sqlite connection helpers
    ├── io/
    │   └── load_csv.py          # load new articleIds from CSV
    ├── services/
    │   ├── pair_indexer.py      # build (articleIdNew × articleIdApproved) pairs
    │   └── urlcheck.py          # compute urlCheck metric
    ├── metrics/                 # placeholder for future metrics
    │   ├── text_hash.py
    │   ├── embeddings.py
    │   └── event_signature.py
    └── utils/
        ├── canonical_url.py     # URL canonicalization logic
        └── timing.py            # simple timing/logging helpers
```

## What NewsNexusDeduper01 Does (v1 Scope)

- **Input**: a CSV file of new `articleId`s (header: `articleId`).
- **Step 1: Pair indexing**
  - Fetch all `articleId`s from the `ArticleApproveds` table (~3k).
  - Create a cartesian product: for each newId × each approvedId, insert a row into `ArticleDuplicateRatings`.
  - Store: `(articleIdNew, articleIdApproved, createdAt, updatedAt)`.
  - Use `INSERT OR IGNORE` + unique index on `(articleIdNew, articleIdApproved)` so the process is **idempotent** (safe to stop/restart).
- **Step 2: Column-by-column metrics (idempotent)**  
  Each metric pass updates only its own column, and only for rows where that column is `NULL` (unless a `--force` option is given):
  1. **URL Canonicalization & Exact Match**
     - Canonicalize both URLs (from the `Articles` table).
     - Populate `urlCheck` = 1 if canonical URLs match, else 0.
  2. **Text Content Hashing**
     - ArticleApproveds table has `content` column
     - SHA-1 for exact matches, SimHash/MinHash for near-duplicates.
     - Populate `contentHash` similarity values.
  3. **Embedding Search**
     - Sentence-transformer embeddings + cosine similarity (or FAISS).
     - Populate `embeddingSearch`.
  4. **Event Signature Matching (future)**
     - Rule-based comparison using spaCy NER, dateparser, etc.
     - Populate fields like `signatureMatchDate`, `signatureMatchState`, etc.
- **Reset Options**
  - A reset command/script can clear the whole `ArticleDuplicateRatings` table.
  - Individual metric columns can be nulled out and recomputed independently.

## Implementation Notes

- Keep each metric module idempotent: compute only missing values unless `--force` is used.
- Database efficiency: use `executemany` batches with WAL mode.
- Logging & monitoring: each run can log number of rows processed.
- Future expansions: add `DeduperRuns` table for metadata (CSV hash, run timestamps, counts).

## Embedding Search Implementation

1. src/metrics/embeddings.py - Full embedding similarity module with:

- Sentence transformer integration using all-MiniLM-L6-v2 model
- Cosine similarity calculation (0.0-1.0 range)
- Smart embedding caching (774 unique articles cached)
- Dual progress bars: Individual batch + overall progress
- Real-time similarity score display

2. Enhanced src/main.py with:

- embeddingsearch subcommand with --model, --batch-size, --force options
- Integration with status command showing embedding progress
- Error handling for missing dependencies
