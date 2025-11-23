# Enterprise-Scale Site Indexer V2

Advanced distributed crawler implementing enterprise-scale concepts from search engines like Bing and Google.

## Architecture Overview

This implementation brings enterprise-scale crawler architecture to a practical Python application:

### 🌐 URL Frontier with Domain-Based Partitioning
- Priority queue for intelligent URL scheduling
- Domain-specific politeness to respect server load
- Deduplication to avoid crawling the same URL twice
- Tracks total enqueued/dequeued for monitoring

### 🔄 Multi-Stage Pipeline

```
Seed URLs → URL Frontier → [Workers] → Fetch → Parse → Normalize → Dedupe → Index
                ↑                                    ↓
                └──────────── Link Discovery ────────┘
```

**Pipeline Stages:**
1. **Fetch**: Download pages (requests or Selenium)
2. **Parse**: Extract title, description, content, links
3. **Normalize**: Clean data, normalize URLs, deduplicate links
4. **Deduplicate**: Hash-based content deduplication
5. **Index**: Store in structured JSON format

### 🗺️ Sitemap Support
- Automatic sitemap discovery from robots.txt
- Parses sitemap.xml and sitemap indexes
- Handles nested sitemaps (sitemap indexes pointing to other sitemaps)
- Prioritizes sitemap URLs for better coverage

### 🤖 Robots.txt Compliance
- Respects robots.txt rules
- Per-domain politeness delays
- Can be disabled with `--no-robots` flag

### ⚡ Multi-Threaded Parallel Crawling
- Configurable number of worker threads (default: 10)
- Each worker has its own fetcher
- Thread-safe URL frontier and result storage
- Real-time progress monitoring

### 🔍 Content Deduplication
- SHA-256 hashing of page content
- Prevents indexing duplicate pages
- Reduces storage and improves quality

### 🚀 Selenium Support
- Optional browser mode for bot protection
- Each worker gets its own browser instance
- Handles JavaScript-rendered content

## Features

✅ **Distributed Architecture**
- URL frontier with priority queue
- Domain-based politeness and rate limiting
- Multi-threaded workers for parallel crawling

✅ **Intelligent URL Discovery**
- Automatic sitemap parsing
- Link extraction and discovery
- Configurable crawl depth

✅ **Content Quality**
- SHA-256 deduplication
- Content normalization
- URL canonicalization

✅ **Politeness & Compliance**
- Robots.txt respect
- Per-domain rate limiting
- Configurable delays

✅ **Dual Fetch Modes**
- Fast requests mode (default)
- Selenium browser mode for protected sites

✅ **Real-Time Monitoring**
- Live progress updates
- Statistics (fetched, failed, duplicates, blocked)
- Queue size monitoring

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For browser mode (optional)
# Install Chrome/Chromium browser
```

## Usage

### Basic Examples

```bash
# Crawl a single site with 10 workers
python site_indexer_v2.py https://example.com

# Crawl multiple sites from file
python site_indexer_v2.py -f urls.txt

# Use 20 workers for faster crawling
python site_indexer_v2.py -f urls.txt -w 20

# Browser mode with 5 workers (slower but bypasses bot detection)
python site_indexer_v2.py -b -w 5 -f urls.txt
```

### Advanced Examples

```bash
# Deep crawl: follow links up to 2 levels
python site_indexer_v2.py --max-depth 2 -w 10 https://example.com

# Aggressive crawling (faster but less polite)
python site_indexer_v2.py -w 50 -d 0.5 -f urls.txt

# Conservative crawling (slower but more polite)
python site_indexer_v2.py -w 5 -d 3.0 -f urls.txt

# Disable robots.txt checking (use responsibly!)
python site_indexer_v2.py --no-robots -w 20 -f urls.txt

# Disable sitemaps (faster startup)
python site_indexer_v2.py --no-sitemaps -w 10 -f urls.txt

# Disable deduplication (keep all pages even if duplicate)
python site_indexer_v2.py --no-dedupe -w 10 -f urls.txt
```

### Browser Mode for Protected Sites

```bash
# Use Selenium for sites with aggressive bot detection
python site_indexer_v2.py -b -w 3 https://tripadvisor.com https://zillow.com

# Browser mode with custom settings
python site_indexer_v2.py -b -w 5 -t 60 -d 2.0 -f protected_sites.txt
```

## Command-Line Options

```
positional arguments:
  urls                  Seed URLs to start crawling

optional arguments:
  -h, --help            Show this help message and exit
  -f FILE, --file FILE  File containing seed URLs (one per line)
  -o OUTPUT, --output OUTPUT
                        Output JSON filename
  -w WORKERS, --workers WORKERS
                        Number of parallel workers (default: 10)
  -t TIMEOUT, --timeout TIMEOUT
                        Request timeout in seconds (default: 30)
  -d DELAY, --delay DELAY
                        Politeness delay per domain in seconds (default: 1.0)
  -b, --use-browser     Use Selenium browser mode
  --no-robots           Disable robots.txt checking
  --no-sitemaps         Disable sitemap discovery
  --no-dedupe           Disable content deduplication
  --max-depth DEPTH     Maximum crawl depth (0 = only seeds, default: 0)
```

## How It Works

### 1. URL Frontier

The URL frontier is a priority queue that manages which URLs to crawl next:

- **Priority levels**: Seeds (10) < Sitemaps (20) < Discovered links (50)
- **Domain politeness**: Tracks last access time per domain
- **Deduplication**: Only adds URLs once to the frontier
- **Thread-safe**: Multiple workers can safely access the queue

### 2. Multi-Stage Pipeline

Each URL goes through 5 stages:

```python
# Stage 1: FETCH
result = fetcher.fetch(url)  # Download page

# Stage 2: PARSE
data = Parser.parse(result)  # Extract title, description, links, content

# Stage 3: NORMALIZE
normalized = Normalizer.normalize(data)  # Clean and normalize data

# Stage 4: DEDUPLICATE
if not deduplicator.is_duplicate(content):  # Check if unique

    # Stage 5: INDEX
    indexed_pages.append(normalized)  # Store result
```

### 3. Sitemap Discovery

On startup, the crawler:

1. Checks robots.txt for `Sitemap:` directives
2. Tries common sitemap locations (`/sitemap.xml`, `/sitemap_index.xml`)
3. Recursively parses sitemap indexes
4. Adds all discovered URLs to frontier with priority 20

### 4. Worker Threads

Each worker thread:

1. Gets URL from frontier (respects domain politeness)
2. Checks robots.txt (if enabled)
3. Fetches page
4. Runs through pipeline (parse → normalize → dedupe → index)
5. Extracts links and adds to frontier (if depth allows)
6. Repeats until frontier is empty

### 5. Deduplication

Content is deduplicated using SHA-256 hashing:

```python
content_hash = sha256(content.encode('utf-8')).hexdigest()
if content_hash not in seen_hashes:
    # Index this page
    seen_hashes.add(content_hash)
```

## Performance Tuning

### Number of Workers

- **Few workers (1-5)**: Slow but polite, good for small sites
- **Medium workers (10-20)**: Balanced, good for most use cases
- **Many workers (30-50+)**: Fast but aggressive, may trigger rate limiting

### Politeness Delay

- **Short delay (0.5s)**: Fast but may trigger rate limiting
- **Medium delay (1-2s)**: Balanced and recommended
- **Long delay (3-5s)**: Very polite, slow crawling

### Browser Mode

- **Pros**: Bypasses bot detection, executes JavaScript
- **Cons**: 3-10x slower, uses more memory
- **Recommendation**: Use 3-5 workers max in browser mode

## Output Format

Same JSON structure as V1:

```json
{
  "Pages": [
    {
      "Url": "https://example.com/page",
      "Title": "Page Title",
      "Description": "Meta description",
      "Content": "Page text content...",
      "Links": ["https://example.com/link1", "https://example.com/link2"],
      "IndexedDate": "2025-01-15T10:30:00"
    }
  ]
}
```

## Performance Comparison

| Metric | V1 (Single Thread) | V2 (10 Workers) | V2 (50 Workers) |
|--------|-------------------|-----------------|-----------------|
| **Speed** | 1-3s per page | 0.5-1s per page | 0.2-0.5s per page |
| **Memory** | Low | Medium | High |
| **Politeness** | Excellent | Good | Fair |
| **Features** | Basic | Full pipeline | Full pipeline |
| **Best For** | Small lists | Medium lists | Large lists |

## Architecture Comparison: V1 vs V2

| Feature | V1 | V2 |
|---------|----|----|
| Threading | Single | Multi (configurable) |
| URL Frontier | No | Yes (priority queue) |
| Sitemap Support | No | Yes (auto-discovery) |
| Robots.txt | No | Yes |
| Deduplication | No | Yes (SHA-256) |
| Pipeline Stages | Integrated | Separated (5 stages) |
| Domain Politeness | Simple delay | Per-domain tracking |
| Link Discovery | No | Yes (configurable depth) |
| Progress Monitoring | tqdm bar | Real-time stats |

## When to Use Each Version

### Use V1 (`site_indexer.py`) when:
- You have a simple list of URLs to index
- You don't need link discovery
- You prefer simplicity
- You're indexing < 100 URLs

### Use V2 (`site_indexer_v2.py`) when:
- You need high performance (parallel crawling)
- You want sitemap support
- You need content deduplication
- You're crawling large sites or many domains
- You want link discovery and deep crawling
- You need robots.txt compliance

## Limitations

- No JavaScript rendering in requests mode (use `-b` for browser mode)
- Browser mode is significantly slower but more reliable
- Large crawls consume memory proportional to unique URLs discovered
- Does not handle CAPTCHA challenges

## Tips & Best Practices

1. **Start conservative**: Begin with 5-10 workers and increase if needed
2. **Respect politeness**: Keep delay at 1s+ to avoid overwhelming servers
3. **Enable robots.txt**: Always respect robots.txt unless you have permission
4. **Use sitemaps**: They significantly improve coverage and efficiency
5. **Monitor progress**: Watch for high failure rates or rate limiting
6. **Deep crawls**: Be careful with `--max-depth > 1`, can discover millions of URLs
7. **Browser mode**: Only use when necessary (for bot-protected sites)
8. **Deduplication**: Keep enabled unless you specifically need duplicate content

## Troubleshooting

### High failure rate
- Reduce number of workers (`-w 5`)
- Increase politeness delay (`-d 2.0`)
- Try browser mode (`-b`)

### Slow crawling
- Increase workers (`-w 20`)
- Decrease delay (`-d 0.5`)
- Disable sitemaps if not needed (`--no-sitemaps`)

### Memory issues
- Reduce workers
- Disable deep crawling (`--max-depth 0`)
- Process URLs in batches

### Bot detection (403 errors)
- Enable browser mode (`-b`)
- Reduce workers in browser mode (`-w 3`)
- Increase delays (`-d 3.0`)

## Examples

### Crawl a list of 1000 sites with optimal settings
```bash
python site_indexer_v2.py -f urls.txt -w 20 -d 1.0 -t 30
```

### Deep crawl a single site
```bash
python site_indexer_v2.py --max-depth 3 -w 10 https://example.com
```

### Handle protected sites with browser mode
```bash
python site_indexer_v2.py -b -w 3 -d 2.0 -f protected_sites.txt
```

### Aggressive crawling for internal network
```bash
python site_indexer_v2.py -w 50 -d 0.2 --no-robots -f internal_urls.txt
```

## License

This project is open source and available for use.
