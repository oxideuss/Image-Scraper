from bs4 import BeautifulSoup
import requests
from pathlib import Path
from urllib.parse import urlparse, urljoin
import re
import json
import logging
import time
import concurrent.futures
from dataclasses import dataclass
from typing import Optional, Deque
from collections import deque
from functools import partial
from datetime import datetime
import yaml
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests.exceptions
from tqdm import tqdm
from threading import Lock

# Configuration
LINKS_FILE = Path("links.txt")
CONFIG_FILE = Path("scraper_config.yaml")

# Map common content-types to extensions
CT_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration for the scraper"""
    timeout: int = 30
    chunk_size: int = 131072  # 128KB
    user_agent: str = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/91.0.4472.124 Safari/537.36")
    max_retries: int = 3
    max_workers: int = 5
    rate_limit_per_second: int = 10
    output_base_dir: Path = Path("./downloads")
    validate_images: bool = True


class RateLimiter:
    """Thread-safe rate limiter for requests"""
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls: Deque[float] = deque()
        self._lock = Lock()

    def wait(self):
        """Wait if rate limit would be exceeded (thread-safe)."""
        with self._lock:
            now = time.time()

            # Remove calls older than the period
            while self.calls and now - self.calls[0] > self.period:
                self.calls.popleft()

            # If we've reached the limit, wait
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)

            self.calls.append(time.time())


def load_config() -> Config:
    """Load configuration from file or use defaults"""
    default_config = {
        "timeout": 30,
        "chunk_size": 131072,
        "user_agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/91.0.4472.124 Safari/537.36"),
        "max_retries": 3,
        "max_workers": 5,
        "rate_limit_per_second": 10,
        "output_base_dir": "./downloads",
        "validate_images": True
    }

    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open('r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}
            default_config.update(user_config)
            logger.info("Configuration loaded from file")
        except Exception as e:
            logger.warning(f"Failed to load config file: {e}. Using defaults.")

    # Convert output_dir to Path
    default_config["output_base_dir"] = Path(default_config["output_base_dir"])

    return Config(**default_config)


def normalize_url(url: str) -> str:
    """Normalize URL removing trailing slash and fragment"""
    url = url.strip()
    if not url:
        return ""

    parsed = urlparse(url)

    # Remove trailing slash from path
    path = parsed.path.rstrip('/')

    # Reconstruct URL without fragment/anchor
    clean_url = parsed._replace(path=path, fragment="").geturl()

    return clean_url


def load_links() -> set[str]:
    """Load previously processed URLs from file"""
    if not LINKS_FILE.exists():
        return set()

    try:
        content = LINKS_FILE.read_text(encoding="utf-8")
        return {normalize_url(line) for line in content.splitlines() if line.strip()}
    except Exception as e:
        logger.error(f"Failed to load links file: {e}")
        return set()


def append_link(url: str) -> None:
    """Append a URL to the links file"""
    try:
        with LINKS_FILE.open("a", encoding="utf-8") as f:
            f.write(url + "\n")
    except Exception as e:
        logger.error(f"Failed to save link: {e}")


def safe_folder_name(name: str) -> str:
    """Create a safe folder name from string"""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r'\s+', ' ', name)  # Replace multiple spaces with single space
    name = name.strip().strip(".")
    return name[:100] if name else "downloaded_images"  # Limit length


def create_output_directory(base_dir: Path, url: str) -> Path:
    """Create organized folder structure for downloads"""
    parsed = urlparse(url)
    domain = parsed.netloc.replace(':', '_').replace('.', '_')
    path_parts = [p for p in parsed.path.split('/') if p]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if path_parts:
        folder_name = f"{timestamp}_{safe_folder_name(path_parts[-1])}"
    else:
        folder_name = f"{timestamp}_{domain}"

    out_dir = base_dir / domain / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    return out_dir


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def scrape_image_urls(page_url: str, config: Config) -> list[str]:
    """Scrape image URLs from the page"""
    headers = {'User-Agent': config.user_agent}

    try:
        resp = requests.get(page_url, timeout=config.timeout, headers=headers)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {page_url}: {e}")
        raise RuntimeError(f"Failed to fetch page: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    image_list = soup.find("ul", {"id": "tiles"})

    if not image_list:
        # Try alternative selectors
        image_list = soup.find("ul", class_=re.compile(r"tiles|gallery|images"))
        if not image_list:
            raise RuntimeError('Could not find image list on the page.')

    urls: list[str] = []
    for item in image_list.find_all("li"):
        a = item.find("a")
        if not a or not a.get("href"):
            continue

        href = a["href"].strip()
        if href:
            urls.append(urljoin(page_url, href))

    if not urls:
        raise RuntimeError("Found the tiles list, but no image links were extracted.")

    # Improvement: de-dupe while preserving order
    urls = list(dict.fromkeys(urls))

    logger.info(f"Found {len(urls)} image URLs on {page_url}")
    return urls


def guess_ext_from_url(img_url: str) -> str | None:
    """Guess file extension from URL"""
    path = urlparse(img_url).path.lower()

    extensions = {
        ".jpg": ".jpg",
        ".jpeg": ".jpg",
        ".png": ".png",
        ".webp": ".webp",
        ".gif": ".gif",
        ".svg": ".svg",
        ".bmp": ".bmp",
        ".tiff": ".tiff",
        ".tif": ".tif"
    }

    for ext_in_url, ext_normalized in extensions.items():
        if path.endswith(ext_in_url):
            return ext_normalized

    return None


def ext_from_content_type(ct: str | None) -> str | None:
    """Get extension from Content-Type header"""
    if not ct:
        return None

    ct = ct.split(";")[0].strip().lower()
    return CT_TO_EXT.get(ct)


def next_available_path(out_dir: Path, base: str, ext: str) -> Path:
    """Find next available filename to avoid overwrites"""
    p = out_dir / f"{base}{ext}"
    if not p.exists():
        return p

    n = 2
    while True:
        candidate = out_dir / f"{base}_{n}{ext}"
        if not candidate.exists():
            return candidate
        n += 1


def validate_image(file_path: Path) -> bool:
    """Check if downloaded file is a valid image"""
    try:
        with Image.open(file_path) as img:
            img.verify()
        return True
    except Exception as e:
        logger.debug(f"Image validation failed for {file_path}: {e}")
        return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def download_single_image(
    img_url: str,
    out_dir: Path,
    index: int,
    config: Config,
    rate_limiter: Optional[RateLimiter] = None
) -> tuple[Path, bool]:
    """Download a single image with retry logic"""

    if rate_limiter:
        rate_limiter.wait()

    base = str(index).zfill(4)
    headers = {'User-Agent': config.user_agent}

    # Improvement: remove HEAD request (less traffic, fewer server quirks).
    # Decide extension from URL first, then from GET Content-Type if needed.
    ext = guess_ext_from_url(img_url) or ".bin"

    with requests.get(img_url, stream=True, timeout=config.timeout, headers=headers) as r:
        r.raise_for_status()

        if ext == ".bin":
            resp_ext = ext_from_content_type(r.headers.get("Content-Type"))
            if resp_ext:
                ext = resp_ext

        dest = next_available_path(out_dir, base, ext)
        out_dir.mkdir(parents=True, exist_ok=True)

        total_size = int(r.headers.get('content-length', 0))

        with open(dest, "wb") as f:
            if total_size == 0:
                for chunk in r.iter_content(chunk_size=config.chunk_size):
                    if chunk:
                        f.write(chunk)
            else:
                with tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=f"IMG {index}",
                    leave=False,
                    disable=total_size < 1024 * 1024
                ) as pbar:
                    for chunk in r.iter_content(chunk_size=config.chunk_size):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

    # Validate image if configured
    if config.validate_images and ext not in [".bin", ".svg"]:
        if not validate_image(dest):
            logger.warning(f"Invalid image detected: {img_url}")
            dest.unlink(missing_ok=True)
            raise ValueError(f"Downloaded file is not a valid image: {img_url}")

    return dest, True


def download_image_wrapper(args, config: Config, rate_limiter: Optional[RateLimiter] = None):
    """Wrapper for concurrent downloads"""
    img_url, out_dir, index = args
    try:
        return download_single_image(img_url, out_dir, index, config, rate_limiter)
    except Exception as e:
        logger.error(f"Failed to download {img_url}: {e}")
        return None, False


def save_metadata(out_dir: Path, url: str, image_urls: list[str], success_count: int):
    """Save metadata about the download session"""
    metadata = {
        "source_url": url,
        "download_date": datetime.now().isoformat(),
        "total_images_found": len(image_urls),
        "successfully_downloaded": success_count,
        "image_urls": image_urls
    }

    metadata_file = out_dir / "metadata.json"
    metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Metadata saved to {metadata_file}")


def prompt_yes_no(prompt: str) -> bool:
    """Prompt user for yes/no answer"""
    while True:
        ans = input(prompt).strip().lower()
        if ans in ("y", "yes", ""):
            return True
        if ans in ("n", "no"):
            return False
        print("Please type Y or N (default is Y):")


def process_url(url: str, config: Config) -> bool:
    """Process a single URL"""
    try:
        logger.info(f"Processing URL: {url}")

        links = load_links()

        if url in links:
            print("\n⚠ WARNING: This URL is already in links.txt.")
            if not prompt_yes_no("Redo scraping this URL? (Y/N) [Y]: "):
                print("Cancelled.")
                return False
        else:
            append_link(url)

        out_dir = create_output_directory(config.output_base_dir, url)
        print(f"\nSaving images to: {out_dir.resolve()}\n")

        image_urls = scrape_image_urls(url, config)

        if not image_urls:
            print("No images found to download.")
            return False

        print(f"Found {len(image_urls)} images to download.\n")

        rate_limiter = RateLimiter(
            max_calls=config.rate_limit_per_second,
            period=1.0
        )

        args_list = [(img_url, out_dir, i) for i, img_url in enumerate(image_urls, 1)]

        successful_downloads = 0
        failed_downloads = 0

        if config.max_workers > 1 and len(image_urls) > 1:
            print(f"Downloading with {config.max_workers} workers...\n")
            with concurrent.futures.ThreadPoolExecutor(max_workers=config.max_workers) as executor:
                download_func = partial(download_image_wrapper, config=config, rate_limiter=rate_limiter)

                with tqdm(total=len(args_list), desc="Overall Progress", unit="img") as pbar:
                    futures = {executor.submit(download_func, args): args for args in args_list}

                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        _, success = result if result else (None, False)
                        if success:
                            successful_downloads += 1
                        else:
                            failed_downloads += 1
                        pbar.update(1)
                        pbar.set_postfix({
                            "success": successful_downloads,
                            "failed": failed_downloads
                        })
        else:
            print("Downloading sequentially...\n")
            for args in tqdm(args_list, desc="Downloading", unit="img"):
                result, success = download_image_wrapper(args, config, rate_limiter)
                if success:
                    successful_downloads += 1
                else:
                    failed_downloads += 1

        save_metadata(out_dir, url, image_urls, successful_downloads)

        print(f"\n{'='*50}")
        print(f"Download Summary:")
        print(f"  Total images found: {len(image_urls)}")
        print(f"  Successfully downloaded: {successful_downloads}")
        print(f"  Failed: {failed_downloads}")
        print(f"  Output directory: {out_dir.resolve()}")
        print(f"{'='*50}\n")

        logger.info(f"Completed processing {url}: {successful_downloads}/{len(image_urls)} images downloaded")

        return successful_downloads > 0

    except Exception as e:
        logger.error(f"Failed to process {url}: {e}")
        print(f"\n❌ Error: {e}\n")
        return False


def main():
    """Main entry point"""
    config = load_config()

    print("\n" + "="*60)
    print("           IMAGE SCRAPER - ENHANCED VERSION")
    print("="*60)
    print(f"Output directory: {config.output_base_dir.resolve()}")
    print(f"Max concurrent downloads: {config.max_workers}")
    print(f"Rate limit: {config.rate_limit_per_second}/second")
    print("="*60)
    print("\nCommands: 'quit', 'exit', or Ctrl+C to stop")
    print("Enter URLs one at a time.\n")

    history = []

    try:
        while True:
            try:
                url_in = input("Enter URL: ").strip()

                if url_in.lower() in ('quit', 'exit', 'q'):
                    break

                if not url_in:
                    continue

                url = normalize_url(url_in)
                if not url.startswith(('http://', 'https://')):
                    print("Please enter a valid URL starting with http:// or https://")
                    continue

                success = process_url(url, config)
                history.append((url, success))

                print("\n" + "-"*40 + "\n")

            except KeyboardInterrupt:
                print("\n\nOperation interrupted. Type 'quit' to exit or enter new URL.")
                continue

    except EOFError:
        print("\n\nEnd of input received.")

    if history:
        print("\n" + "="*60)
        print("                    SESSION SUMMARY")
        print("="*60)
        total = len(history)
        successful = sum(1 for _, success in history if success)
        print(f"Total URLs processed: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {total - successful}")

        if successful > 0:
            print(f"\nCheck {config.output_base_dir.resolve()} for downloaded images")
            print(f"See scraper.log for detailed logs")
        print("="*60)

    print("\nGoodbye!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Fatal error in main:")
        print(f"\n❌ Fatal error occurred: {e}")
        print("Check scraper.log for details.")
