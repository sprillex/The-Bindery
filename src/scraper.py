
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

    def scrape_feed(self, feed_url, scrape_full_article=True):
        feed = feedparser.parse(feed_url)
        articles = []

        print(f"Scraping feed: {feed.feed.get('title', feed_url)}")

        for entry in feed.entries:
            article_url = entry.link
            title = entry.title
            print(f"Processing article: {title}")

            try:
                if scrape_full_article:
                    content, assets = self.scrape_article_from_url(article_url)
                else:
                    # Extract content from RSS
                    rss_content = ""
                    if 'content' in entry:
                        for c in entry.content:
                            if c.type == 'text/html':
                                rss_content += c.value
                    elif 'summary' in entry:
                        rss_content = entry.summary

                    if not rss_content:
                        # Fallback if no content in RSS, try scraping anyway?
                        # Or just provide a link? Let's just provide a link.
                        rss_content = f"<p>No content available in RSS. <a href='{article_url}'>Read full article</a></p>"

                    content, assets = self.process_html_content(rss_content, article_url, title)

                articles.append({
                    'title': title,
                    'url': article_url,
                    'content': content,
                    'assets': assets
                })
            except Exception as e:
                print(f"Failed to scrape {article_url}: {e}")

        return articles

    def scrape_article_from_url(self, url):
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.title.string if soup.title else 'Article'

        # We need the whole body
        content_html = str(soup.body) if soup.body else str(soup)

        return self.process_html_content(content_html, url, title)

    def process_html_content(self, html_content, base_url, title):
        soup = BeautifulSoup(html_content, 'html.parser')

        # Basic cleanup: remove scripts, styles, etc.
        for script in soup(["script", "style", "iframe", "noscript"]):
            script.decompose()

        # Remove "Skip to content" links
        for a in soup.find_all('a'):
            if a.get_text(strip=True).lower() in ['skip to content', 'skip to main content', 'skip navigation']:
                a.decompose()
            elif a.get('href', '').startswith('#') and 'content' in a.get('href', '').lower() and 'skip' in a.get_text(strip=True).lower():
                # Handles links like <a href="#content">Skip</a>
                a.decompose()

        # Remove elements with common skip-link classes/ids
        for skip in soup.select('.skip-link, #skip-link, .skip-to-content, #skip-to-content'):
            skip.decompose()

        assets = []

        # Download images and rewrite src
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue

            abs_url = urljoin(base_url, src)

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

        # Return the cleaned HTML wrapped in standard page
        # If the input was just a fragment (like from RSS), body might not exist in soup if we didn't wrap it.
        # But BeautifulSoup usually handles fragments.

        body_content = str(soup.body) if soup.body else str(soup)

        full_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>{title}</title>
        </head>
        <body>
            <h1>{title}</h1>
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
    articles = scraper.scrape_feed("http://feeds.bbci.co.uk/news/rss.xml", scrape_full_article=False)
    print(f"Scraped {len(articles)} articles.")
