#!/usr/bin/env python3
"""
Site Indexer - Index websites and generate JSON output
"""
import json
import sys
from datetime import datetime
from typing import List, Dict
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


class SiteIndexer:
    """Main class for indexing websites"""

    def __init__(self, timeout: int = 30):
        """
        Initialize the site indexer

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def fetch_page(self, url: str) -> tuple:
        """
        Fetch a webpage

        Args:
            url: The URL to fetch

        Returns:
            tuple: (content, status_code) or (None, error_code)
        """
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            return response.text, response.status_code
        except requests.RequestException as e:
            tqdm.write(f"Error fetching {url}: {e}", file=sys.stderr)
            return None, -1

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract all links from the page

        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links

        Returns:
            List of absolute URLs
        """
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            if absolute_url not in links:
                links.append(absolute_url)
        return links

    def extract_text_content(self, soup: BeautifulSoup) -> str:
        """
        Extract readable text content from the page

        Args:
            soup: BeautifulSoup object

        Returns:
            Cleaned text content
        """
        # Remove script and style elements
        for script in soup(['script', 'style', 'nav', 'footer', 'header']):
            script.decompose()

        # Get text
        text = soup.get_text(separator=' ', strip=True)

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text

    def extract_description(self, soup: BeautifulSoup) -> str:
        """
        Extract page description from meta tags

        Args:
            soup: BeautifulSoup object

        Returns:
            Description text
        """
        # Try meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content']

        # Try og:description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content']

        # Fallback: first paragraph or truncated content
        first_p = soup.find('p')
        if first_p:
            text = first_p.get_text(strip=True)
            return text[:300] + '...' if len(text) > 300 else text

        return ""

    def extract_title(self, soup: BeautifulSoup) -> str:
        """
        Extract page title

        Args:
            soup: BeautifulSoup object

        Returns:
            Page title
        """
        # Try title tag
        if soup.title and soup.title.string:
            return soup.title.string.strip()

        # Try og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content']

        # Try h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        return "Untitled"

    def index_url(self, url: str) -> Dict:
        """
        Index a single URL

        Args:
            url: The URL to index

        Returns:
            Dictionary with indexed data
        """
        content, status = self.fetch_page(url)

        if content is None:
            tqdm.write(f"Failed to fetch {url}", file=sys.stderr)
            return None

        soup = BeautifulSoup(content, 'html.parser')

        # Extract all data
        # Note: extract links BEFORE text content, as text extraction modifies soup
        title = self.extract_title(soup)
        description = self.extract_description(soup)
        links = self.extract_links(soup, url)
        text_content = self.extract_text_content(soup)

        # Create page data matching the required format
        page_data = {
            "Url": url,
            "Title": title,
            "Description": description,
            "Content": text_content,
            "Links": links,
            "IndexedDate": datetime.now().isoformat()
        }

        return page_data

    def index_sites(self, urls: List[str]) -> Dict:
        """
        Index multiple URLs

        Args:
            urls: List of URLs to index

        Returns:
            Dictionary with Pages array
        """
        pages = []

        # Use tqdm for progress bar
        for url in tqdm(urls, desc="Indexing sites", unit="site"):
            page_data = self.index_url(url)
            if page_data:
                pages.append(page_data)

        return {"Pages": pages}

    def save_to_json(self, data: Dict, filename: str = None):
        """
        Save indexed data to JSON file

        Args:
            data: Data to save
            filename: Output filename (default: indexed_sites_TIMESTAMP.json)
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"indexed_sites_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\nIndexed data saved to: {filename}")
        return filename


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Index websites and generate JSON output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index a single site
  python site_indexer.py https://example.com

  # Index multiple sites
  python site_indexer.py https://example.com https://github.com

  # Specify output filename
  python site_indexer.py -o output.json https://example.com

  # Read URLs from a file (one URL per line)
  python site_indexer.py -f urls.txt
        """
    )

    parser.add_argument(
        'urls',
        nargs='*',
        help='URLs to index'
    )

    parser.add_argument(
        '-f', '--file',
        help='Read URLs from a file (one per line)'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output filename (default: indexed_sites_TIMESTAMP.json)'
    )

    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=30,
        help='Request timeout in seconds (default: 30)'
    )

    args = parser.parse_args()

    # Collect URLs
    urls = list(args.urls) if args.urls else []

    if args.file:
        try:
            with open(args.file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    # Split by whitespace to handle multiple URLs per line
                    line_urls = line.split()
                    urls.extend(line_urls)
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found", file=sys.stderr)
            sys.exit(1)

    if not urls:
        parser.print_help()
        print("\nError: No URLs provided", file=sys.stderr)
        sys.exit(1)

    # Validate URLs
    valid_urls = []
    for url in urls:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            print(f"Warning: Invalid URL skipped: {url}", file=sys.stderr)
        else:
            valid_urls.append(url)

    if not valid_urls:
        print("Error: No valid URLs to index", file=sys.stderr)
        sys.exit(1)

    # Index sites
    indexer = SiteIndexer(timeout=args.timeout)
    data = indexer.index_sites(valid_urls)

    # Save results
    output_file = indexer.save_to_json(data, args.output)

    print(f"\nSuccessfully indexed {len(data['Pages'])} of {len(valid_urls)} site(s)")


if __name__ == '__main__':
    main()
