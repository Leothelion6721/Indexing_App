#!/usr/bin/env python3
"""
Enterprise-Scale Site Indexer
Implements distributed crawler concepts:
- URL frontier with domain-based partitioning
- Multi-stage pipeline (fetch → parse → normalize → dedupe → index)
- Sitemap support for URL discovery
- Multi-threaded parallel crawling
- Content deduplication
- Robots.txt compliance
"""

import requests
import hashlib
import json
import sys
import time
import random
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin, parse_qs
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Thread, Lock, Semaphore
from queue import PriorityQueue, Empty
import xml.etree.ElementTree as ET

try:
    from bs4 import BeautifulSoup
    import urllib.robotparser
except ImportError:
    print("Error: Required packages not installed. Run: pip install beautifulsoup4 lxml", file=sys.stderr)
    sys.exit(1)

# Optional: Selenium support
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


@dataclass
class URLFrontierItem:
    """Item in the URL frontier queue"""
    priority: int  # Lower = higher priority
    timestamp: float
    url: str
    depth: int = 0
    source: str = "seed"  # seed, sitemap, link

    def __lt__(self, other):
        # Priority queue ordering
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


@dataclass
class CrawlResult:
    """Result from fetching a URL"""
    url: str
    status_code: int
    content: Optional[str] = None
    links: List[str] = field(default_factory=list)
    error: Optional[str] = None


class URLFrontier:
    """
    URL Frontier with domain-based partitioning and politeness
    Coordinates URL discovery and crawl scheduling
    """

    def __init__(self, politeness_delay: float = 1.0):
        self.queue = PriorityQueue()
        self.seen_urls: Set[str] = set()
        self.domain_queues: Dict[str, deque] = defaultdict(deque)
        self.domain_last_access: Dict[str, float] = {}
        self.politeness_delay = politeness_delay
        self.lock = Lock()
        self.total_enqueued = 0
        self.total_dequeued = 0

    def add_url(self, url: str, priority: int = 50, depth: int = 0, source: str = "seed"):
        """Add URL to frontier if not seen"""
        with self.lock:
            if url in self.seen_urls:
                return False

            self.seen_urls.add(url)
            item = URLFrontierItem(
                priority=priority,
                timestamp=time.time(),
                url=url,
                depth=depth,
                source=source
            )
            self.queue.put(item)
            self.total_enqueued += 1
            return True

    def add_urls(self, urls: List[str], priority: int = 50, depth: int = 0, source: str = "seed"):
        """Bulk add URLs"""
        added = 0
        for url in urls:
            if self.add_url(url, priority, depth, source):
                added += 1
        return added

    def get_url(self, timeout: float = 1.0) -> Optional[URLFrontierItem]:
        """Get next URL respecting domain politeness"""
        try:
            item = self.queue.get(timeout=timeout)

            # Check politeness delay for domain
            domain = urlparse(item.url).netloc
            with self.lock:
                last_access = self.domain_last_access.get(domain, 0)
                wait_time = last_access + self.politeness_delay - time.time()

                if wait_time > 0:
                    time.sleep(wait_time)

                self.domain_last_access[domain] = time.time()
                self.total_dequeued += 1

            return item

        except Empty:
            return None

    def size(self) -> int:
        """Return number of URLs in queue"""
        return self.queue.qsize()

    def is_empty(self) -> bool:
        """Check if frontier is empty"""
        return self.queue.empty()


class SitemapParser:
    """Parse XML sitemaps and sitemap indexes"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()

    def discover_sitemap(self, base_url: str) -> List[str]:
        """Try to discover sitemap from common locations"""
        parsed = urlparse(base_url)
        sitemap_urls = [
            f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap-index.xml",
        ]

        # Check robots.txt for sitemap
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            resp = self.session.get(robots_url, timeout=self.timeout)
            if resp.status_code == 200:
                for line in resp.text.split('\n'):
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        sitemap_urls.insert(0, sitemap_url)
        except:
            pass

        return sitemap_urls

    def parse_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse sitemap and return list of URLs"""
        try:
            resp = self.session.get(sitemap_url, timeout=self.timeout)
            if resp.status_code != 200:
                return []

            urls = []
            root = ET.fromstring(resp.content)

            # Handle sitemap index (points to other sitemaps)
            if 'sitemapindex' in root.tag:
                for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                    # Recursively parse referenced sitemaps
                    urls.extend(self.parse_sitemap(sitemap.text))

            # Handle regular sitemap
            elif 'urlset' in root.tag:
                for loc in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                    urls.append(loc.text)

            return urls

        except Exception as e:
            return []


class RobotsTxtChecker:
    """Check robots.txt compliance"""

    def __init__(self, user_agent: str = "*", timeout: int = 5):
        self.user_agent = user_agent
        self.timeout = timeout
        self.parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self.failed_domains: Set[str] = set()  # Domains where robots.txt failed
        self.lock = Lock()

    def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt"""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        with self.lock:
            # If we already know this domain's robots.txt failed, allow crawling
            if base_url in self.failed_domains:
                return True

            if base_url not in self.parsers:
                rp = urllib.robotparser.RobotFileParser()
                rp.set_url(f"{base_url}/robots.txt")
                try:
                    # Use requests with timeout instead of rp.read() which can hang
                    import requests
                    resp = requests.get(f"{base_url}/robots.txt", timeout=self.timeout)
                    if resp.status_code == 200:
                        rp.parse(resp.text.splitlines())
                    else:
                        # robots.txt not found or error, allow crawling
                        self.failed_domains.add(base_url)
                        return True
                except:
                    # If robots.txt can't be fetched, allow crawling and remember this domain
                    self.failed_domains.add(base_url)
                    return True
                self.parsers[base_url] = rp

            parser = self.parsers[base_url]

        return parser.can_fetch(self.user_agent, url)

    def get_crawl_delay(self, url: str) -> Optional[float]:
        """Get crawl delay from robots.txt"""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        with self.lock:
            if base_url in self.parsers:
                delay = self.parsers[base_url].crawl_delay(self.user_agent)
                return float(delay) if delay else None
        return None


class ContentDeduplicator:
    """Deduplicate content using hashing"""

    def __init__(self):
        self.seen_hashes: Set[str] = set()
        self.lock = Lock()

    def get_content_hash(self, content: str) -> str:
        """Generate hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def is_duplicate(self, content: str) -> bool:
        """Check if content is duplicate"""
        content_hash = self.get_content_hash(content)

        with self.lock:
            if content_hash in self.seen_hashes:
                return True
            self.seen_hashes.add(content_hash)
            return False

    def mark_as_seen(self, content: str):
        """Mark content as seen"""
        content_hash = self.get_content_hash(content)
        with self.lock:
            self.seen_hashes.add(content_hash)


class Fetcher:
    """
    Fetch stage: Download web pages
    Supports both requests and Selenium modes
    """
    # Class-level lock to prevent simultaneous browser initialization
    _browser_init_lock = Lock()

    def __init__(self, timeout: int = 30, use_browser: bool = False):
        self.timeout = timeout
        self.use_browser = use_browser
        self.driver: Optional[uc.Chrome] = None

        if use_browser:
            if not SELENIUM_AVAILABLE:
                raise ImportError("Selenium required for browser mode")
            self._init_browser()
        else:
            self.session = requests.Session()
            self._setup_session()

    def _setup_session(self):
        """Setup requests session with browser-like headers"""
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        ]
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def _init_browser(self):
        """Initialize Selenium browser"""
        # Use lock to prevent simultaneous initialization across workers
        with Fetcher._browser_init_lock:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            self.driver.set_page_load_timeout(self.timeout)
            # Small delay to ensure ChromeDriver files are fully released
            time.sleep(0.5)

    def fetch(self, url: str) -> CrawlResult:
        """Fetch URL and return result"""
        if self.use_browser:
            return self._fetch_browser(url)
        else:
            return self._fetch_requests(url)

    def _fetch_requests(self, url: str) -> CrawlResult:
        """Fetch using requests library"""
        try:
            # Rotate user agent
            self.session.headers['User-Agent'] = random.choice(self.user_agents)

            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)

            return CrawlResult(
                url=url,
                status_code=resp.status_code,
                content=resp.text if resp.status_code == 200 else None
            )

        except Exception as e:
            return CrawlResult(
                url=url,
                status_code=0,
                error=str(e)
            )

    def _fetch_browser(self, url: str) -> CrawlResult:
        """Fetch using Selenium browser"""
        try:
            # Set page load timeout
            self.driver.set_page_load_timeout(self.timeout)

            # Try to load the page
            self.driver.get(url)

            # Wait for body to load with explicit timeout
            WebDriverWait(self.driver, min(self.timeout, 10)).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Small delay to ensure page is fully loaded
            time.sleep(random.uniform(1, 2))

            content = self.driver.page_source

            return CrawlResult(
                url=url,
                status_code=200,
                content=content
            )

        except Exception as e:
            # If page load times out or fails, try to get whatever content is available
            try:
                content = self.driver.page_source
                if content and len(content) > 100:  # If we got some content
                    return CrawlResult(
                        url=url,
                        status_code=200,
                        content=content
                    )
            except:
                pass

            return CrawlResult(
                url=url,
                status_code=0,
                error=str(e)
            )

    def cleanup(self):
        """Cleanup resources"""
        if self.use_browser and self.driver:
            try:
                self.driver.quit()
            except:
                pass


class Parser:
    """
    Parse stage: Extract data from HTML
    """

    @staticmethod
    def parse(result: CrawlResult) -> Dict:
        """Parse HTML and extract data"""
        if not result.content:
            return None

        soup = BeautifulSoup(result.content, 'html.parser')

        # Extract title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Extract description
        description = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            meta_desc = soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc and meta_desc.get('content'):
            description = meta_desc['content'].strip()

        # Extract links
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            absolute_url = urljoin(result.url, href)
            if absolute_url.startswith('http'):
                links.append(absolute_url)

        # Extract text content
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()

        text_content = soup.get_text(separator=' ', strip=True)
        # Clean up whitespace
        text_content = ' '.join(text_content.split())

        return {
            "url": result.url,
            "title": title,
            "description": description,
            "content": text_content[:10000],  # Limit content length
            "links": links,
            "status_code": result.status_code
        }


class Normalizer:
    """
    Normalize stage: Clean and normalize data
    """

    @staticmethod
    def normalize(data: Dict) -> Dict:
        """Normalize parsed data"""
        if not data:
            return None

        # Normalize URL (remove fragments, sort query params)
        parsed = urlparse(data['url'])
        normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            # Sort query parameters for consistency
            params = parse_qs(parsed.query)
            sorted_params = '&'.join(f"{k}={v[0]}" for k, v in sorted(params.items()))
            normalized_url += f"?{sorted_params}"

        # Normalize text content (lowercase, remove extra spaces)
        content = data['content']
        if content:
            content = ' '.join(content.split())

        # Deduplicate links
        links = list(set(data['links']))

        return {
            "Url": normalized_url,
            "Title": data['title'][:500],  # Limit title length
            "Description": data['description'][:1000],  # Limit description
            "Content": content,
            "Links": links,
            "IndexedDate": datetime.now().isoformat()
        }


class DistributedCrawler:
    """
    Main crawler coordinating URL frontier, workers, and pipeline
    """

    def __init__(
        self,
        num_workers: int = 5,
        politeness_delay: float = 1.0,
        timeout: int = 30,
        use_browser: bool = False,
        respect_robots: bool = True,
        use_sitemaps: bool = True,
        max_depth: int = 0,
        deduplicate: bool = True,
        verbose: bool = False
    ):
        self.num_workers = num_workers
        self.timeout = timeout
        self.use_browser = use_browser
        self.respect_robots = respect_robots
        self.use_sitemaps = use_sitemaps
        self.max_depth = max_depth
        self.deduplicate_enabled = deduplicate
        self.verbose = verbose

        # Initialize components
        self.frontier = URLFrontier(politeness_delay=politeness_delay)
        self.sitemap_parser = SitemapParser(timeout=timeout)
        self.robots_checker = RobotsTxtChecker(timeout=5) if respect_robots else None
        self.deduplicator = ContentDeduplicator() if deduplicate else None

        # Results
        self.indexed_pages: List[Dict] = []
        self.lock = Lock()
        self.stats = {
            'fetched': 0,
            'failed': 0,
            'duplicates': 0,
            'robots_blocked': 0
        }

        # Worker threads
        self.workers: List[Thread] = []
        self.running = False

    def add_seeds(self, urls: List[str]):
        """Add seed URLs to frontier"""
        added = self.frontier.add_urls(urls, priority=10, source="seed")
        print(f"Added {added} seed URLs to frontier")

        # Discover sitemaps if enabled
        if self.use_sitemaps:
            self._discover_sitemaps(urls)

    def _discover_sitemaps(self, urls: List[str]):
        """Discover and parse sitemaps for seed URLs"""
        print("Discovering sitemaps...")
        sitemap_urls_found = 0

        for url in urls:
            sitemap_locations = self.sitemap_parser.discover_sitemap(url)
            for sitemap_url in sitemap_locations:
                print(f"  Parsing sitemap: {sitemap_url}")
                sitemap_urls = self.sitemap_parser.parse_sitemap(sitemap_url)
                added = self.frontier.add_urls(sitemap_urls, priority=20, source="sitemap")
                sitemap_urls_found += added
                if added > 0:
                    print(f"    Found {added} URLs")

        if sitemap_urls_found > 0:
            print(f"Total sitemap URLs added: {sitemap_urls_found}")

    def _worker(self, worker_id: int):
        """Worker thread that processes URLs from frontier"""
        # Each worker gets its own fetcher
        fetcher = Fetcher(timeout=self.timeout, use_browser=self.use_browser)

        try:
            while self.running:
                # Get URL from frontier
                item = self.frontier.get_url(timeout=1.0)
                if item is None:
                    continue

                # Check depth limit
                if self.max_depth > 0 and item.depth > self.max_depth:
                    continue

                # Check robots.txt
                if self.respect_robots and self.robots_checker:
                    if not self.robots_checker.can_fetch(item.url):
                        if self.verbose:
                            print(f"[Worker {worker_id}] Blocked by robots.txt: {item.url}")
                        with self.lock:
                            self.stats['robots_blocked'] += 1
                        continue

                # STAGE 1: FETCH
                if self.verbose:
                    print(f"[Worker {worker_id}] Fetching: {item.url}")

                result = fetcher.fetch(item.url)

                if result.error or not result.content:
                    if self.verbose:
                        print(f"[Worker {worker_id}] Failed: {item.url} - {result.error}")
                    with self.lock:
                        self.stats['failed'] += 1
                    continue

                if self.verbose:
                    print(f"[Worker {worker_id}] Success: {item.url}")

                with self.lock:
                    self.stats['fetched'] += 1

                # STAGE 2: PARSE
                parsed_data = Parser.parse(result)
                if not parsed_data:
                    continue

                # STAGE 3: NORMALIZE
                normalized_data = Normalizer.normalize(parsed_data)
                if not normalized_data:
                    continue

                # STAGE 4: DEDUPLICATE
                if self.deduplicate_enabled and self.deduplicator:
                    if self.deduplicator.is_duplicate(normalized_data['Content']):
                        with self.lock:
                            self.stats['duplicates'] += 1
                        continue

                # STAGE 5: INDEX (store result)
                with self.lock:
                    self.indexed_pages.append(normalized_data)

                # Discover new URLs from links (if depth allows)
                # Only follow links if max_depth > 0 and we haven't reached the limit
                if self.max_depth > 0 and item.depth < self.max_depth:
                    for link in parsed_data['links'][:50]:  # Limit links per page
                        self.frontier.add_url(link, priority=50, depth=item.depth + 1, source="link")

        finally:
            fetcher.cleanup()

    def crawl(self):
        """Start crawling"""
        self.running = True

        print(f"\nStarting distributed crawler with {self.num_workers} workers...")
        print(f"URL frontier size: {self.frontier.size()}")
        print(f"Settings: robots.txt={self.respect_robots}, sitemaps={self.use_sitemaps}, dedupe={self.deduplicate_enabled}")
        print()

        # Start worker threads
        for i in range(self.num_workers):
            worker = Thread(target=self._worker, args=(i,), daemon=True)
            worker.start()
            self.workers.append(worker)

        # Monitor progress
        try:
            while self.running:
                time.sleep(2)

                with self.lock:
                    indexed = len(self.indexed_pages)
                    fetched = self.stats['fetched']
                    failed = self.stats['failed']
                    duplicates = self.stats['duplicates']

                queue_size = self.frontier.size()

                print(f"\rIndexed: {indexed} | Fetched: {fetched} | Failed: {failed} | Duplicates: {duplicates} | Queue: {queue_size}", end='', flush=True)

                # Stop if frontier is empty and workers are done
                if queue_size == 0 and self.frontier.total_enqueued == self.frontier.total_dequeued:
                    time.sleep(2)  # Wait a bit more to ensure workers are done
                    if queue_size == 0:
                        break

        except KeyboardInterrupt:
            print("\n\nStopping crawler...")

        finally:
            self.running = False

            # Wait for workers to finish
            for worker in self.workers:
                worker.join(timeout=5)

            print(f"\n\nCrawl complete!")
            print(f"Total indexed: {len(self.indexed_pages)}")
            print(f"Total fetched: {self.stats['fetched']}")
            print(f"Total failed: {self.stats['failed']}")
            print(f"Total duplicates: {self.stats['duplicates']}")
            print(f"Robots.txt blocked: {self.stats['robots_blocked']}")

    def get_results(self) -> Dict:
        """Get indexed results"""
        return {"Pages": self.indexed_pages}

    def save_to_json(self, filename: str = None):
        """Save results to JSON"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"indexed_sites_{timestamp}.json"

        data = self.get_results()

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Results saved to: {filename}")
        return filename


def main():
    parser = argparse.ArgumentParser(
        description='Enterprise-Scale Distributed Site Indexer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic crawl with 10 workers
  python site_indexer_v2.py -w 10 https://example.com

  # Crawl from URL file with sitemaps
  python site_indexer_v2.py -f urls.txt -w 20

  # Browser mode for bot protection
  python site_indexer_v2.py -b -w 5 -f urls.txt

  # Deep crawl (follow links up to 2 levels)
  python site_indexer_v2.py --max-depth 2 -w 10 https://example.com
        """
    )

    parser.add_argument('urls', nargs='*', help='Seed URLs to start crawling')
    parser.add_argument('-f', '--file', help='File containing seed URLs (one per line)')
    parser.add_argument('-o', '--output', help='Output JSON filename')
    parser.add_argument('-w', '--workers', type=int, default=10, help='Number of parallel workers (default: 10)')
    parser.add_argument('-t', '--timeout', type=int, default=30, help='Request timeout in seconds (default: 30)')
    parser.add_argument('-d', '--delay', type=float, default=1.0, help='Politeness delay per domain in seconds (default: 1.0)')
    parser.add_argument('-b', '--use-browser', action='store_true', help='Use Selenium browser mode')
    parser.add_argument('--no-robots', action='store_true', help='Disable robots.txt checking')
    parser.add_argument('--no-sitemaps', action='store_true', help='Disable sitemap discovery')
    parser.add_argument('--no-dedupe', action='store_true', help='Disable content deduplication')
    parser.add_argument('--max-depth', type=int, default=0, help='Maximum crawl depth (0 = only seeds, default: 0)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed progress for each URL')

    args = parser.parse_args()

    # Collect URLs
    urls = list(args.urls) if args.urls else []

    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    # Handle multiple URLs per line
                    urls.extend(line.split())
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
        print("Error: No valid URLs", file=sys.stderr)
        sys.exit(1)

    # Create crawler
    crawler = DistributedCrawler(
        num_workers=args.workers,
        politeness_delay=args.delay,
        timeout=args.timeout,
        use_browser=args.use_browser,
        respect_robots=not args.no_robots,
        use_sitemaps=not args.no_sitemaps,
        max_depth=args.max_depth,
        deduplicate=not args.no_dedupe,
        verbose=args.verbose
    )

    # Add seed URLs
    crawler.add_seeds(valid_urls)

    # Start crawl
    crawler.crawl()

    # Save results
    crawler.save_to_json(args.output)


if __name__ == '__main__':
    main()
