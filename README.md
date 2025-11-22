# Site Indexer

A Python application that indexes websites and generates structured JSON output with page content, metadata, and links.

## Features

- Index single or multiple websites
- Extract page title, description, content, and all links
- Output JSON in a structured format
- Support for both command-line arguments and URL files
- Real-time progress bar when indexing multiple sites
- Automatic handling of relative URLs
- Timestamps for indexed pages
- Error handling and retry logic

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

## Requirements

- Python 3.6+
- requests >= 2.31.0
- beautifulsoup4 >= 4.12.0
- lxml >= 4.9.0
- tqdm >= 4.66.0

## Limitations

- Only indexes the HTML content of pages (no JavaScript rendering)
- Large pages may take time to process
- Some sites may block automated requests (respect robots.txt)
- Rate limiting is not built-in (add delays between requests if needed)

## Tips

1. **Respect robots.txt**: Always check if a site allows crawling
2. **Rate limiting**: Consider adding delays between requests for multiple pages
3. **Large batches**: For indexing many sites, run in batches to avoid timeouts
4. **Memory usage**: Very large pages or many pages at once may use significant memory

## License

This project is open source and available for use.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.
