# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NewsNexus Deduper is a Python-based news article deduplication system that identifies potential duplicate articles from the NewsNexus Database. It processes new article IDs from CSV files and compares them against approved articles using multiple algorithms.

## Architecture

### Project Structure
```
NewsNexusDeduper01/
├── docs/
│   ├── DEDUPER_OVERVIEW.md      # detailed technical architecture
│   └── DATABASE_SCHEMA_OVERVIEW.md  # complete database schema
├── src/
│   ├── main.py                  # CLI entry point with subcommands
│   ├── config.py                # environment and config values
│   ├── db.py                    # sqlite connection helpers
│   ├── io/
│   │   └── load_csv.py          # load new articleIds from CSV
│   ├── services/
│   │   ├── pair_indexer.py      # build (articleIdNew × articleIdApproved) pairs
│   │   └── urlcheck.py          # compute urlCheck metric
│   ├── metrics/                 # future metrics modules
│   │   ├── text_hash.py
│   │   ├── embeddings.py
│   │   └── event_signature.py
│   └── utils/
│       ├── canonical_url.py     # URL canonicalization logic
│       └── timing.py            # timing/logging helpers
├── .env                         # environment configuration
└── README.md
```

### Core Processing Pipeline
1. **CSV Loading**: Load new article IDs from CSV (header: `articleId`)
2. **Pair Indexing**: Create cartesian product of new articles × approved articles (~3k)
3. **Metric Computation**: Run idempotent similarity algorithms:
   - URL canonicalization and exact matching
   - Text content hashing (future)
   - Embedding-based similarity (future)
   - Event signature matching (future)

### Database Integration
- Uses SQLite database via the existing NewsNexus08Db schema
- Main target table: `ArticleDuplicateRatings` with columns for each similarity metric
- References `Articles` and `ArticleApproveds` tables
- All operations are idempotent using `INSERT OR IGNORE` with unique constraints

## Environment Configuration

Required environment variables in `.env`:
- `PATH_TO_DATABASE`: Directory path for database file
- `NAME_DB`: Database filename
- `PATH_TO_PYTHON_VENV`: Python virtual environment path
- `PATH_TO_CSV`: Path to article IDs CSV file

## Development Setup

### Python Environment
This project uses a Python virtual environment. Activate it with:
```bash
source /Users/nick/Documents/_environments/deduper/bin/activate
```

### Current Implementation Status
The project is in early development phase. The planned module structure exists in documentation but the actual Python implementation is not yet created.

## Key Design Principles

1. **Idempotency**: All operations can be safely rerun without duplication
2. **Incremental Processing**: Metrics computed independently, can be rerun per column
3. **Batch Efficiency**: Uses `executemany` with WAL mode for database operations
4. **Extensibility**: Modular metric system for adding new similarity algorithms

## Database Schema Key Points

- `ArticleDuplicateRatings` table stores pairwise similarity scores
- Unique constraint on `(articleIdNew, articleIdApproved)` prevents duplicates
- Similarity scores are floats in 0-1 range, initially NULL
- Multiple algorithm columns: `urlCheck`, `contentHash`, `embeddingSearch`, signature matches
- Final composite scores in `score` and `scoreWeighted` columns