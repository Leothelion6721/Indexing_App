#!/usr/bin/env python3
"""
Site Indexer - Index websites and generate JSON output
"""
import json
import sys
import time
import random
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Optional Selenium imports (only needed if using browser mode)
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    uc = None


class SiteIndexer:
    """Main class for indexing websites"""

    def __init__(self, timeout: int = 30, max_retries: int = 3, delay: float = 0.5, use_browser: bool = False):
        """
        Initialize the site indexer

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            delay: Delay in seconds between requests (to avoid rate limiting)
            use_browser: If True, use Selenium with undetected Chrome (slower but bypasses all bot detection)
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay = delay
        self.use_browser = use_browser
        self.driver: Optional[uc.Chrome] = None

        if use_browser:
            if not SELENIUM_AVAILABLE:
                raise ImportError("Selenium and undetected-chromedriver are required for browser mode. Install with: pip install selenium undetected-chromedriver")
            self._init_browser()
        else:
            self.session = requests.Session()
            # Enable cookie handling
            self.session.cookies.set_policy = True

        # Expanded list of User-Agent strings including mobile
        self.user_agents = [
            # Chrome Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Chrome macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Firefox Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            # Firefox macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
            # Safari macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            # Chrome Linux
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            # Edge Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
            # Mobile Chrome
            'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36',
            # Mobile Safari
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
        ]

        if not use_browser:
            self._update_headers()

    def _init_browser(self):
        """Initialize undetected Chrome browser"""
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        # Run headless for faster performance (optional)
        # options.add_argument('--headless=new')

        self.driver = uc.Chrome(options=options, use_subprocess=True)
        self.driver.set_page_load_timeout(self.timeout)

    def __del__(self):
        """Cleanup browser on object destruction"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

    def _update_headers(self, user_agent_index: int = 0, url: str = None):
        """
        Update session headers with more browser-like headers

        Args:
            user_agent_index: Index of user agent to use from the list
            url: The URL being requested (for Referer header)
        """
        user_agent = self.user_agents[user_agent_index % len(self.user_agents)]

        # Randomly choose a search engine referer to make it look organic
        referers = [
            'https://www.google.com/',
            'https://www.bing.com/',
            'https://duckduckgo.com/',
            'https://search.yahoo.com/',
            'https://www.ecosia.org/',
            None  # Sometimes no referer
        ]
        referer = random.choice(referers)

        # Detect if User-Agent is mobile
        is_mobile = 'Mobile' in user_agent or 'iPhone' in user_agent or 'Android' in user_agent

        # Base headers that all browsers send
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # Add language with slight variation
        languages = [
            'en-US,en;q=0.9',
            'en-US,en;q=0.9,en-GB;q=0.8',
            'en-GB,en-US;q=0.9,en;q=0.8',
            'en-US,en;q=0.9,es;q=0.8',
        ]
        headers['Accept-Language'] = random.choice(languages)

        # Add cache control (randomly)
        if random.choice([True, False]):
            headers['Cache-Control'] = 'max-age=0'

        # Add referer if we have one
        if referer:
            headers['Referer'] = referer

        # Add Chrome/Chromium-specific headers (for Chrome-based UAs)
        if 'Chrome' in user_agent or 'Edg' in user_agent:
            headers['Sec-Fetch-Dest'] = 'document'
            headers['Sec-Fetch-Mode'] = 'navigate'
            headers['Sec-Fetch-Site'] = 'cross-site' if referer else 'none'
            headers['Sec-Fetch-User'] = '?1'
            headers['sec-ch-ua'] = '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"'
            headers['sec-ch-ua-mobile'] = '?1' if is_mobile else '?0'
            headers['sec-ch-ua-platform'] = '"Android"' if is_mobile else '"Windows"'

        # Add DNT header randomly (not all users have it)
        if random.choice([True, False, False]):  # 33% chance
            headers['DNT'] = '1'

        self.session.headers.clear()
        self.session.headers.update(headers)

    def _fetch_page_browser(self, url: str) -> tuple:
        """
        Fetch a webpage using Selenium browser

        Args:
            url: The URL to fetch

        Returns:
            tuple: (content, status_code) or (None, error_code)
        """
        try:
            self.driver.get(url)
            # Wait for body to load
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Small delay to ensure page is fully loaded
            time.sleep(random.uniform(1, 2))

            content = self.driver.page_source
            return content, 200
        except Exception as e:
            tqdm.write(f"Browser error fetching {url}: {str(e)}", file=sys.stderr)
            return None, -1

    def fetch_page(self, url: str) -> tuple:
        """
        Fetch a webpage with retry logic

        Args:
            url: The URL to fetch

        Returns:
            tuple: (content, status_code) or (None, error_code)
        """
        # If using browser mode, use Selenium
        if self.use_browser:
            return self._fetch_page_browser(url)

        # Otherwise use requests with retry logic
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Add delay between requests (except for first attempt)
                if attempt > 0:
                    # Exponential backoff: 1s, 2s, 4s, etc.
                    backoff_time = 2 ** attempt
                    time.sleep(backoff_time)

                    # On retry, try a different User-Agent to bypass bot detection
                    self._update_headers(attempt, url)

                # Add small random delay to avoid pattern detection (100-500ms)
                time.sleep(random.uniform(0.1, 0.5))

                response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                response.raise_for_status()
                return response.text, response.status_code

            except requests.exceptions.Timeout as e:
                last_error = f"Timeout (attempt {attempt + 1}/{self.max_retries})"
                continue

            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error (attempt {attempt + 1}/{self.max_retries})"
                continue

            except requests.exceptions.HTTPError as e:
                # Special handling for 403 Forbidden - might be bot detection
                if response.status_code == 403:
                    if attempt < self.max_retries - 1:
                        last_error = f"HTTP 403 Forbidden (attempt {attempt + 1}/{self.max_retries}), trying different User-Agent"
                        # Try again with different User-Agent
                        continue
                    else:
                        last_error = f"HTTP 403: Forbidden (bot detection)"
                        break
                # Special handling for 429 Too Many Requests - rate limiting
                elif response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        # Add extra delay for rate limiting
                        extra_delay = 3 * (2 ** attempt)  # 3s, 6s, 12s, etc.
                        last_error = f"HTTP 429 Too Many Requests (attempt {attempt + 1}/{self.max_retries}), waiting {extra_delay}s"
                        tqdm.write(f"Rate limited on {url}, waiting {extra_delay}s before retry...", file=sys.stderr)
                        time.sleep(extra_delay)
                        continue
                    else:
                        last_error = f"HTTP 429: Too Many Requests (rate limited)"
                        break
                # Retry on server errors (5xx)
                elif response.status_code >= 500:
                    last_error = f"Server error {response.status_code} (attempt {attempt + 1}/{self.max_retries})"
                    continue
                else:
                    # Other client errors like 404 - don't retry
                    last_error = f"HTTP {response.status_code}: {e}"
                    break

            except requests.exceptions.TooManyRedirects as e:
                last_error = f"Too many redirects"
                break

            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {e}"
                continue

        # All retries failed
        if last_error:
            tqdm.write(f"Failed to fetch {url}: {last_error}", file=sys.stderr)

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
        # Reset headers to default for each new URL
        self._update_headers(0, url)

        content, status = self.fetch_page(url)

        if content is None:
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
        for i, url in enumerate(tqdm(urls, desc="Indexing sites", unit="site")):
            page_data = self.index_url(url)
            if page_data:
                pages.append(page_data)

            # Add delay between requests (except for last one)
            # Add randomization to make timing more human-like
            if i < len(urls) - 1 and self.delay > 0:
                # Randomize delay ±30% to avoid patterns
                actual_delay = self.delay * random.uniform(0.7, 1.3)
                time.sleep(actual_delay)

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

  # Use more retries and longer delay for problematic sites
  python site_indexer.py -r 5 -d 1.0 -f urls.txt

  # Increase timeout for slow sites
  python site_indexer.py -t 60 -r 5 https://slow-site.com

  # Use real browser for sites with advanced bot protection
  python site_indexer.py -b -f urls.txt

  # Combine browser mode with other options
  python site_indexer.py -b -r 5 -d 2.0 -f urls.txt
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

    parser.add_argument(
        '-r', '--retries',
        type=int,
        default=3,
        help='Maximum number of retry attempts for failed requests (default: 3)'
    )

    parser.add_argument(
        '-d', '--delay',
        type=float,
        default=0.5,
        help='Delay in seconds between requests to avoid rate limiting (default: 0.5)'
    )

    parser.add_argument(
        '-b', '--use-browser',
        action='store_true',
        help='Use real Chrome browser (Selenium) for maximum bot bypass (slower but works on all sites)'
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
    indexer = SiteIndexer(
        timeout=args.timeout,
        max_retries=args.retries,
        delay=args.delay,
        use_browser=args.use_browser
    )
    data = indexer.index_sites(valid_urls)

    # Save results
    output_file = indexer.save_to_json(data, args.output)

    print(f"\nSuccessfully indexed {len(data['Pages'])} of {len(valid_urls)} site(s)")


if __name__ == '__main__':
    main()
