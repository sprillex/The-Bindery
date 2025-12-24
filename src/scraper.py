
import feedparser
import requests
from bs4 import BeautifulSoup
import os
import hashlib
from urllib.parse import urljoin, urlparse

class Scraper:
    def __init__(self, download_dir):
        self.download_dir = download_dir
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

    def scrape_feed(self, feed_url):
        feed = feedparser.parse(feed_url)
        articles = []

        print(f"Scraping feed: {feed.feed.get('title', feed_url)}")

        for entry in feed.entries:
            article_url = entry.link
            title = entry.title
            print(f"Processing article: {title}")

            try:
                content, assets = self.scrape_article(article_url)
                articles.append({
                    'title': title,
                    'url': article_url,
                    'content': content,
                    'assets': assets
                })
            except Exception as e:
                print(f"Failed to scrape {article_url}: {e}")

        return articles

    def scrape_article(self, url):
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Basic cleanup: remove scripts, styles, etc.
        for script in soup(["script", "style", "iframe", "noscript"]):
            script.decompose()

        assets = []

        # Download images and rewrite src
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue

            abs_url = urljoin(url, src)

            # Generate a filename for the image
            ext = os.path.splitext(urlparse(abs_url).path)[1]
            if not ext:
                ext = ".jpg" # Default

            filename = hashlib.md5(abs_url.encode('utf-8')).hexdigest() + ext

            # Download image
            try:
                img_data = self.download_asset(abs_url)
                if img_data:
                    assets.append({'filename': filename, 'data': img_data})
                    img['src'] = filename
            except Exception as e:
                print(f"Failed to download image {abs_url}: {e}")

        # Return the cleaned HTML body
        # We wrap it in a basic template to make it a full page
        body_content = str(soup.body) if soup.body else str(soup)

        full_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>{soup.title.string if soup.title else 'Article'}</title>
        </head>
        <body>
            {body_content}
        </body>
        </html>
        """

        return full_html, assets

    def download_asset(self, url):
        try:
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200:
                return response.content
        except Exception:
            pass
        return None

if __name__ == "__main__":
    # Test with a sample feed
    scraper = Scraper("test_downloads")
    # Using a reliable feed for testing
    articles = scraper.scrape_feed("http://feeds.bbci.co.uk/news/rss.xml")
    print(f"Scraped {len(articles)} articles.")
