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
- **Advanced bot detection bypass - Maximum stealth**
  - Rotates through **13 different User-Agent strings** (Chrome, Firefox, Safari, Edge, Mobile)
  - Random Referer headers from 6 sources (Google, Bing, Yahoo, DuckDuckGo, Ecosia, or none)
  - **Randomized header combinations** - Cache-Control (50% chance), DNT (33% chance)
  - Variable Accept-Language headers (4 different combinations)
  - Platform-specific headers for mobile vs desktop browsers
  - **Humanized timing patterns**:
    - Per-request jitter: 100-500ms random delay
    - Per-site delay: ±30% randomization (e.g., 0.5s → 0.35-0.65s)
  - Proper cookie handling and session persistence
  - Chrome-specific headers (sec-ch-ua, Sec-Fetch-*) added conditionally
  - Maximum diversity to avoid fingerprinting and pattern detection
- **Rate limiting protection**
  - Configurable delay between requests (default: 0.5s)
  - Prevents triggering anti-bot measures
- **Selenium browser mode for maximum bypass**
  - Optional real Chrome browser automation using undetected-chromedriver
  - Bypasses virtually all bot detection (Cloudflare, PerimeterX, DataDome, etc.)
  - Executes JavaScript and handles complex anti-bot challenges
  - Trade-off: Slower but more reliable for heavily protected sites
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

3. (Optional) For Selenium browser mode:
   - Install Google Chrome or Chromium browser
   - The `undetected-chromedriver` package will automatically download the matching ChromeDriver
   - On Linux: `sudo apt-get install chromium-browser` or `google-chrome-stable`
   - On macOS: `brew install --cask google-chrome`
   - On Windows: Download from [google.com/chrome](https://www.google.com/chrome/)

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

Use Selenium browser mode for heavily protected sites:
```bash
python site_indexer.py -b https://tripadvisor.com
```

Combine browser mode with other options:
```bash
python site_indexer.py -b -t 60 -d 2.0 -f urls.txt
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
  -b, --use-browser     Use Selenium with real Chrome browser for maximum bot bypass (slower but more reliable)
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
- selenium >= 4.15.0 (for browser mode)
- undetected-chromedriver >= 3.5.0 (for browser mode)

## Browser Mode vs Requests Mode

### When to Use Requests Mode (Default)
- **Fast and efficient** - Processes pages quickly with minimal resource usage
- **Good for most sites** - Works with 90%+ of websites
- **Ideal for batch processing** - Can handle hundreds of sites efficiently
- **Use when**: Sites don't have aggressive bot detection

### When to Use Browser Mode (`-b` flag)
- **Maximum bypass capability** - Uses a real Chrome browser to appear as a human user
- **JavaScript execution** - Handles sites that require JavaScript to load content
- **Complex anti-bot systems** - Bypasses Cloudflare, PerimeterX, DataDome, and similar protections
- **Challenging sites** - Sites like TripAdvisor, Zillow, or other heavily protected platforms
- **Trade-offs**: Slower (3-10x), uses more memory and CPU, requires Chrome installed
- **Use when**: Sites return 403 Forbidden or show CAPTCHA challenges with requests mode

### Performance Comparison
| Mode | Speed | Success Rate | Resource Usage | Bot Bypass |
|------|-------|--------------|----------------|------------|
| Requests (default) | Fast (1-3s per page) | 85-95% | Low | Good |
| Browser (`-b`) | Slow (5-15s per page) | 98-100% | High | Excellent |

**Recommendation**: Start with requests mode for speed. If you encounter persistent 403 errors or bot detection, switch to browser mode for those specific sites.

## Limitations

- **Requests mode**: Only indexes static HTML content (no JavaScript rendering)
- **Browser mode**: Executes JavaScript but is significantly slower
- Large pages may take time to process
- Some sites may block automated requests despite all bypass techniques (always respect robots.txt)
- Browser mode requires Chrome/Chromium to be installed

## Tips

1. **Respect robots.txt**: Always check if a site allows crawling
2. **For unreliable sites**: Use `-r 5` or higher to increase retry attempts
3. **Avoid rate limiting**: Use `-d 1.0` or higher to add delays between requests
4. **Large batches**: Combine `-t 60 -r 5 -d 1.0` for maximum robustness when indexing many sites
5. **Memory usage**: Very large pages or many pages at once may use significant memory
6. **Server errors vs client errors**: The tool automatically retries server errors (5xx) and special client errors (403, 429), but not other client errors (404, etc.) to save time
7. **Rate limiting (429 errors)**: The tool automatically handles rate limiting with extended delays, but if you frequently hit 429 errors, increase the `-d` delay parameter
8. **Persistent 403 Forbidden errors**: If requests mode consistently fails with 403 errors, switch to browser mode (`-b`) for maximum bot bypass
9. **Browser mode performance**: When using `-b`, increase the delay (`-d 2.0` or higher) since browser mode is already slower
10. **Hybrid approach**: Use requests mode for most sites, then re-run failed URLs with browser mode for maximum efficiency

## License

This project is open source and available for use.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.
