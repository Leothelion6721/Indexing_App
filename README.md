# Site Indexer

A Python application that indexes websites and generates structured JSON output with page content, metadata, and links.

## Features

- Index single or multiple websites
- Extract page title, description, content, and all links
- Output JSON in a structured format
- Support for both command-line arguments and URL files
- Real-time progress bar when indexing multiple sites
- **Robust error handling with automatic retry logic**
  - Exponential backoff retry for failed requests
  - Configurable retry attempts (default: 3)
  - Smart retry: only retries timeouts, connection errors, and server errors (5xx)
  - Special handling for 403 errors with User-Agent rotation
  - Special handling for 429 errors with extended delays (rate limiting)
  - Skips retry on other client errors (404, etc.) to save time
- **Advanced bot detection bypass**
  - Automatically rotates through 5 different realistic User-Agent strings
  - Random Referer headers (Google, Bing, DuckDuckGo) to simulate organic traffic
  - Randomized request timing (100-500ms jitter) to avoid pattern detection
  - Mimics real browser behavior with comprehensive headers
  - Includes Chrome-specific headers (sec-ch-ua, Sec-Fetch-*, etc.)
  - Significantly improves success rate for sites with sophisticated bot protection
- **Rate limiting protection**
  - Configurable delay between requests (default: 0.5s)
  - Prevents triggering anti-bot measures
- Automatic handling of relative URLs
- Timestamps for indexed pages
- Comprehensive error reporting

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd Indexing_App
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Index a single website:
```bash
python site_indexer.py https://example.com
```

Index multiple websites:
```bash
python site_indexer.py https://example.com https://github.com https://stackoverflow.com
```

### Advanced Options

Specify output filename:
```bash
python site_indexer.py -o my_index.json https://example.com
```

Read URLs from a file:
```bash
python site_indexer.py -f urls.txt
```

Set custom timeout (in seconds):
```bash
python site_indexer.py -t 60 https://example.com
```

Increase retry attempts for unreliable sites:
```bash
python site_indexer.py -r 5 -f urls.txt
```

Add delay between requests to avoid rate limiting:
```bash
python site_indexer.py -d 1.0 -f urls.txt
```

Combine options for maximum robustness:
```bash
python site_indexer.py -t 60 -r 5 -d 1.0 -f urls.txt
```

### Using a URL File

Create a text file (e.g., `urls.txt`) with one URL per line:
```
https://example.com
https://github.com
https://stackoverflow.com
# This is a comment - lines starting with # are ignored
```

Then run:
```bash
python site_indexer.py -f urls.txt
```

## Command-Line Options

```
positional arguments:
  urls                  URLs to index

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  Read URLs from a file (one per line)
  -o OUTPUT, --output OUTPUT
                        Output filename (default: indexed_sites_TIMESTAMP.json)
  -t TIMEOUT, --timeout TIMEOUT
                        Request timeout in seconds (default: 30)
  -r RETRIES, --retries RETRIES
                        Maximum number of retry attempts for failed requests (default: 3)
  -d DELAY, --delay DELAY
                        Delay in seconds between requests to avoid rate limiting (default: 0.5)
```

## Output Format

The application generates a JSON file with the following structure:

```json
{
  "Pages": [
    {
      "Url": "https://example.com",
      "Title": "Example Domain",
      "Description": "Example Domain description from meta tags",
      "Content": "Full text content of the page...",
      "Links": [
        "https://example.com/page1",
        "https://example.com/page2"
      ],
      "IndexedDate": "2025-11-21T19:30:00.123456"
    }
  ]
}
```

### Field Descriptions

- **Url**: The URL of the indexed page
- **Title**: Page title extracted from `<title>` tag, og:title, or `<h1>`
- **Description**: Page description from meta tags or first paragraph
- **Content**: Full text content of the page (scripts, styles, and navigation removed)
- **Links**: Array of all absolute URLs found on the page
- **IndexedDate**: ISO format timestamp of when the page was indexed

## Output File Location

By default, JSON files are created in the same directory where the script runs with the naming pattern:
- `indexed_sites_YYYYMMDD_HHMMSS.json`

You can specify a custom filename with the `-o` option.

## Examples

### Example 1: Quick Single Site Index
```bash
python site_indexer.py https://example.com
# Output: indexed_sites_20251121_193000.json
```

### Example 2: Multiple Sites with Custom Output
```bash
python site_indexer.py -o tech_sites.json https://github.com https://stackoverflow.com
# Output: tech_sites.json
```

### Example 3: Batch Indexing from File
Create `sites_to_index.txt`:
```
https://example.com
https://github.com
https://stackoverflow.com
```

Run:
```bash
python site_indexer.py -f sites_to_index.txt -o batch_index.json
# Output: batch_index.json
```

### Example 4: Long Timeout for Slow Sites
```bash
python site_indexer.py -t 120 https://slow-website.com
# Uses 120-second timeout instead of default 30 seconds
```

## Error Handling

The application includes robust error handling:
- Invalid URLs are skipped with a warning
- Failed requests are logged but don't stop the entire process
- Network errors are caught and reported
- Invalid file paths are handled gracefully
- **403 Forbidden errors**: Automatically retries with different User-Agent strings
- **429 Too Many Requests**: Retries with extended delays (3s, 6s, 12s) to respect rate limits
- **Server errors (5xx)**: Retries with exponential backoff
- **Timeouts and connection errors**: Automatic retry with backoff
- **Other client errors (404, etc.)**: Skipped to save time

## Requirements

- Python 3.6+
- requests >= 2.31.0
- beautifulsoup4 >= 4.12.0
- lxml >= 4.9.0
- tqdm >= 4.66.0

## Limitations

- Only indexes the HTML content of pages (no JavaScript rendering)
- Large pages may take time to process
- Some sites may block automated requests despite retries (respect robots.txt)

## Tips

1. **Respect robots.txt**: Always check if a site allows crawling
2. **For unreliable sites**: Use `-r 5` or higher to increase retry attempts
3. **Avoid rate limiting**: Use `-d 1.0` or higher to add delays between requests
4. **Large batches**: Combine `-t 60 -r 5 -d 1.0` for maximum robustness when indexing many sites
5. **Memory usage**: Very large pages or many pages at once may use significant memory
6. **Server errors vs client errors**: The tool automatically retries server errors (5xx) and special client errors (403, 429), but not other client errors (404, etc.) to save time
7. **Rate limiting (429 errors)**: The tool automatically handles rate limiting with extended delays, but if you frequently hit 429 errors, increase the `-d` delay parameter

## License

This project is open source and available for use.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.
