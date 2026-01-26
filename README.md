# 📸 Enhanced Image Scraper

A robust, feature-rich Python image scraper with concurrent downloading, rate limiting, validation, and comprehensive logging. Perfect for archiving image galleries from various websites.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

## ✨ Features

- **🔄 Concurrent Downloads**: Download multiple images simultaneously with configurable thread pool
- **⚡ Rate Limiting**: Built-in rate limiter to avoid overwhelming servers
- **✅ Image Validation**: Automatic validation of downloaded images using PIL
- **📁 Organized Storage**: Automatic folder organization by domain and timestamp
- **📊 Progress Tracking**: Real-time progress bars with tqdm
- **🔁 Retry Logic**: Exponential backoff retry for failed downloads
- **📝 Comprehensive Logging**: File and console logging
- **🎯 Configurable**: YAML-based configuration system
- **💾 Metadata Preservation**: Saves JSON metadata with each download session
- **🛡️ Safe Filenames**: Automatically sanitizes folder and file names
- **🚦 Graceful Handling**: Continue processing after individual download failures

## 📋 Prerequisites

- Python 3.10 or higher
- pip package manager

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/image-scraper.git
cd image-scraper
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

**Or install manually:**
```bash
pip install beautifulsoup4 requests pillow tqdm tenacity pyyaml
```

## ⚡ Quick Start

python scraper.py  
Enter a gallery URL  
Watch images download  


## 📁 Project Structure

```
image-scraper/
├── scraper.py              # Main scraper script
├── scraper_config.yaml     # Configuration file (optional)
├── links.txt              # History of processed URLs
├── scraper.log            # Log file (auto-generated)
├── downloads/             # Default download directory
│   ├── example_com/
│   │   └── 20240126_143022_gallery_name/
│   │       ├── 0001.jpg
│   │       ├── 0002.png
│   │       └── metadata.json
│   └── ...
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## ⚙️ Configuration

Create a `scraper_config.yaml` file to customize behavior:

```yaml
# Basic Configuration Example
timeout: 30
max_workers: 5
rate_limit_per_second: 3
output_base_dir: "./my_images"
validate_images: true
```

See the [Configuration Guide](#configuration-options) for all available options.

## 🎯 Usage

### Basic Usage
```bash
python scraper.py
```

### Interactive Mode
When you run the script, you'll see:
```
============================================================
           IMAGE SCRAPER - ENHANCED VERSION
============================================================
Output directory: /path/to/downloads
Max concurrent downloads: 5
Rate limit: 3/second
============================================================

Commands: 'quit', 'exit', or Ctrl+C to stop
Enter URLs one at a time.

Enter URL: https://example.com/gallery
```

### Example Workflow
1. Run the script: `python scraper.py`
2. Enter a gallery URL when prompted
3. Watch real-time progress with progress bars
4. View summary when complete
5. Enter next URL or type `quit` to exit

## 🔧 Configuration Options

### Network Settings
```yaml
timeout: 45                    # Request timeout in seconds
chunk_size: 262144             # Download chunk size (256KB)
max_retries: 5                 # Retry attempts for failed downloads
user_agent: "Mozilla/5.0..."  # Custom User-Agent string
```

### Concurrency
```yaml
max_workers: 8                 # Number of concurrent downloads
rate_limit_per_second: 5       # Max requests per second
```

### File Handling
```yaml
output_base_dir: "./scraped_images"  # Base download directory
validate_images: true          # Validate downloaded images
```

### Advanced Options (Soon)


## 📝 How It Works

### 1. URL Processing
- Normalizes URL (removes trailing slashes, fragments)
- Checks against `links.txt` history
- Prompts for confirmation if URL was previously processed

### 2. Scraping
- Fetches HTML content from the URL
- Parses with BeautifulSoup
- Looks for `<ul id="tiles">` or similar gallery structures
- Extracts all image links

### 3. Downloading
- Creates organized folder structure: `domain/YYYYMMDD_HHMMSS_gallery_name/`
- Downloads images concurrently with rate limiting
- Validates each image after download
- Retries failed downloads (up to configured limit)
- Saves metadata about the download session

### 4. Organization
```
downloads/
└── example_com/
    └── 20240126_143022_my_gallery/
        ├── 0001.jpg
        ├── 0002.jpg
        ├── 0003.png
        └── metadata.json      # Contains URL list, timestamps, stats
```

## 🎨 Customization

### Extending for Different Sites
The scraper is designed for `<ul id="tiles">` structures. To adapt for other sites:

1. Modify the `scrape_image_urls()` function
2. Update the BeautifulSoup selectors
3. Adjust URL joining logic as needed

### Adding File Formats
Extend the content-type mappings in the configuration:
```yaml
content_type_mappings:
  "image/jpeg": ".jpg"
  "image/png": ".png"
  "image/webp": ".webp"
  "image/gif": ".gif"
  "image/svg+xml": ".svg"
  "image/bmp": ".bmp"
  "image/tiff": ".tiff"
```

## 📊 Output Examples

### Console Output
```
Found 24 images to download.
Downloading with 5 workers...

Overall Progress: 100%|██████████| 24/24 [00:45<00:00,  0.53img/s, success=22, failed=2]

==================================================
Download Summary:
  Total images found: 24
  Successfully downloaded: 22
  Failed: 2
  Output directory: /downloads/example_com/20240126_143022_gallery
==================================================
```

### Log File (`scraper.log`)
```
2024-01-26 14:30:22,123 - INFO - Processing URL: https://example.com/gallery
2024-01-26 14:30:25,456 - INFO - Found 24 image URLs on https://example.com/gallery
2024-01-26 14:30:45,789 - INFO - Metadata saved to /downloads/.../metadata.json
2024-01-26 14:30:46,123 - INFO - Completed processing https://example.com/gallery: 22/24 images downloaded
```

### Metadata File (`metadata.json`)
```json
{
  "source_url": "https://example.com/gallery",
  "download_date": "2024-01-26T14:30:22.123456",
  "total_images_found": 24,
  "successfully_downloaded": 22,
  "image_urls": [
    "https://example.com/image1.jpg",
    "https://example.com/image2.jpg",
    "..."
  ]
}
```

## 🚨 Error Handling

The scraper handles various errors gracefully:

- **Network failures**: Retry with exponential backoff
- **Invalid images**: Delete corrupted files automatically
- **Missing elements**: Provide clear error messages
- **Rate limiting**: Automatic slowdown with configurable limits
- **Disk full**: Catch and report storage errors
- **Permission issues**: Report file access problems

## 🎯 Performance Tips

### For Fast Connections
```yaml
max_workers: 10
chunk_size: 524288      # 512KB chunks
rate_limit_per_second: 10
```

### For Rate-Limited Sites
```yaml
max_workers: 2
rate_limit_per_second: 1
timeout: 60
```

### For Unstable Connections
```yaml
max_retries: 10
timeout: 120
chunk_size: 32768       # 32KB chunks
```

## 🔍 Troubleshooting

### Common Issues

1. **"Could not find image list on the page"**
   - The site may use a different HTML structure
   - Modify the `scrape_image_urls()` function selectors

2. **Slow downloads**
   - Check your internet connection
   - Reduce `max_workers` in config
   - Increase `timeout` value

3. **Permission denied errors**
   - Run as administrator/root if needed
   - Check output directory permissions
   - Specify a different `output_base_dir`

4. **Images not validating**
   - Try setting `validate_images: false`
   - Check if file format is supported in `CT_TO_EXT`

### Debug Mode
Enable detailed logging by changing the log level in configuration:
```yaml
log_level: "DEBUG"
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -m 'Add some feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a Pull Request

### Development Setup
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest

# Code formatting
black scraper.py
```

## 🛣 Planned Features

- Custom request headers from config
- Domain-specific settings
- Resume interrupted downloads
- Skip / size filters
- Content-type override mappings
- Proxy authentication helpers
- Filename templates
- WebP → PNG conversion

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- [Requests](https://requests.readthedocs.io/) for HTTP client
- [Pillow](https://python-pillow.org/) for image validation
- [tqdm](https://tqdm.github.io/) for progress bars
- [Tenacity](https://tenacity.readthedocs.io/) for retry logic

## ⚠️ Disclaimer

This tool is for educational purposes and personal use only. Always:
- Respect website terms of service
- Check `robots.txt` before scraping
- Don't overload servers with excessive requests
- Only download content you have permission to access
- Respect copyright and intellectual property rights

The developers are not responsible for misuse of this software.

---

**Happy Scraping!** 🎨 If you find this tool useful, please consider giving it a ⭐ on GitHub!
