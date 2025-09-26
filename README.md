# NewsNexus Deduper

This is a Python script that identifies potential duplicate news articles from the NewsNexus Database.

- detailed project overview in [docs/DEDUPER_OVERVIEW.md](docs/DEDUPER_OVERVIEW.md)
- database schema overview in [docs/DATABASE_SCHEMA_OVERVIEW.md](docs/DATABASE_SCHEMA_OVERVIEW.md)

## .env

```
PATH_TO_DATABASE=/Users/nick/Documents/_databases/NewsNexus08
NAME_DB=newsnexus08.db
PATH_TO_PYTHON_VENV=/Users/nick/Documents/_environments/deduper
PATH_TO_CSV=/Users/nick/Documents/_project_resources/NewsNexus08/utilities/deduper/article_ids.csv
```

- these are actual Mac workstation values

## How to run

All commands must be executed from the `src/` directory:

```bash
cd src
```

### Main Commands

#### 1. Check Status

View current database statistics and counts:

```bash
python main.py status
```

Shows:

- Total ArticleDuplicateRatings rows
- Number of unique new articles
- Number of unique approved articles
- Articles loaded from CSV

#### 2. Load Article Pairs

Load article IDs from CSV and create pairwise combinations with approved articles:

**Using default CSV path from .env:**

```bash
python main.py load
```

**Using custom CSV file:**

```bash
python main.py load --csv-path /path/to/your/articles.csv
```

**Force reload existing pairs:**

```bash
python main.py load --force
```

The load command:

- Reads article IDs from CSV file (must have `articleId` header)
- Validates that articles exist in the database
- Creates cartesian product: new articles × approved articles
- Inserts pairs into ArticleDuplicateRatings table
- Uses `INSERT OR IGNORE` for idempotent operations
- Processes in batches of 1000 for efficiency

#### 3. Clear Database

Clear all data from ArticleDuplicateRatings table:

```bash
python main.py reset --confirm
```

**Warning:** This permanently deletes all duplicate rating data. The `--confirm` flag is required as a safety measure.

#### 4. Compute URL Similarity

Compute URL similarity scores by comparing canonicalized URLs between article pairs:

**Process all pending URL comparisons:**

```bash
python main.py urlcheck
```

**Recompute all URL scores (including existing ones):**

```bash
python main.py urlcheck --force
```

**Custom batch size for processing:**

```bash
python main.py urlcheck --batch-size 500
```

The urlcheck command:

- Processes article pairs where `urlCheck` is NULL
- Canonicalizes URLs by removing protocol, www, trailing slashes, etc.
- Compares canonicalized URLs for exact matches
- Sets `urlCheck` to 1.0 for exact matches, 0.0 for non-matches
- Processes in configurable batches (default: 1000 pairs)
- Updates progress statistics shown in `status` command

#### 5. Compute Content Hash Similarity

Compute content hash similarity scores by comparing normalized headline and text content:

**Process all pending content hash comparisons:**

```bash
python main.py contenthash
```

**Recompute all content hash scores (including existing ones):**

```bash
python main.py contenthash --force
```

The contenthash command:

- Processes article pairs where `contentHash` is NULL
- Uses `headlineForPdfReport` and `textForPdfReport` from ArticleApproveds table
- Normalizes text by converting to lowercase, removing punctuation, and collapsing whitespace
- Generates SHA-256 hashes of combined headline and text content
- Sets `contentHash` to 1.0 for exact content matches, 0.0 for non-matches
- Processes in batches of 1000 pairs with progress reporting
- Updates progress statistics shown in `status` command

### Help Commands

Get help for any command:

```bash
python main.py --help
python main.py load --help
python main.py reset --help
python main.py status --help
python main.py urlcheck --help
python main.py contenthash --help
```

### Prerequisites

- Python 3.8+
- Activate the virtual environment: `source /Users/nick/Documents/_environments/deduper/bin/activate`
- Valid `.env` file with database and CSV paths
- NewsNexus database with Articles, ArticleApproveds, and ArticleDuplicateRatings tables

## Claude Code Tasks

### First task for claude code

- create module and code to load new articleIds from CSV
- populate the ArticleDuplicateRatings table with the articleIds from the CSV and ArticleApproveds table
- create function to clear the ArticleDuplicateRatings table that can be triggered from the terminal as well

### Second task for claude code

- create module and code to compute urlCheck metric
