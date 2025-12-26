
import libzim
from libzim.writer import Creator, Item, StringProvider, Hint, ContentProvider, Blob
import hashlib

class InMemoryContentProvider(ContentProvider):
    def __init__(self, content):
        super().__init__()
        if isinstance(content, str):
            self.content = content.encode('utf-8')
        else:
            self.content = content
        self.size = len(self.content)
        self.fed = False

    def get_size(self):
        return self.size

    def feed(self):
        if self.fed:
            return Blob(b"")
        self.fed = True
        return Blob(self.content)

class ZimItem(Item):
    def __init__(self, path, content, mimetype, title=None, hints=None):
        super().__init__()
        self.path = path
        self.content = content
        self.mimetype = mimetype
        self._title = title
        self._hints = hints or {}

    def get_path(self):
        return self.path

    def get_title(self):
        return self._title or ""

    def get_mimetype(self):
        return self.mimetype

    def get_contentprovider(self):
        return InMemoryContentProvider(self.content)

    def get_hints(self):
        return self._hints

class ZimBuilder:
    def __init__(self, filename):
        self.filename = filename
        self.articles = []

    def add_article(self, article):
        self.articles.append(article)

    def build(self):
        creator = Creator(self.filename)
        creator.config_indexing(True, "eng")

        with creator:
            # Create index page content
            index_html = "<html><head><title>Index</title></head><body><h1>Articles</h1><ul>"

            # Let's restart the loop structure to handle deduplication
            added_paths = set()

            for article in self.articles:
                # Generate slug for article
                slug = hashlib.md5(article['url'].encode('utf-8')).hexdigest() + ".html"

                # Add assets first
                for asset in article.get('assets', []):
                    asset_path = asset['filename']
                    if asset_path not in added_paths:
                        # Guess mimetype
                        mimetype = "image/jpeg"
                        if asset_path.endswith(".png"): mimetype = "image/png"
                        elif asset_path.endswith(".gif"): mimetype = "image/gif"

                        item = ZimItem(asset_path, asset['data'], mimetype)
                        creator.add_item(item)
                        added_paths.add(asset_path)

                # Add article
                if slug not in added_paths:
                    item = ZimItem(slug, article['content'], "text/html", title=article['title'], hints={Hint.FRONT_ARTICLE: True})
                    creator.add_item(item)
                    added_paths.add(slug)

                    index_html += f'<li><a href="{slug}">{article["title"]}</a></li>'

            index_html += "</ul></body></html>"

            # Add index page
            index_path = "index.html"
            if index_path not in added_paths:
                item = ZimItem(index_path, index_html, "text/html", title="Index", hints={Hint.FRONT_ARTICLE: True})
                creator.add_item(item)

            # If there is only one article, make it the main page
            if len(self.articles) == 1:
                # Re-calculate slug for the single article to set as mainpath
                article = self.articles[0]
                slug = hashlib.md5(article['url'].encode('utf-8')).hexdigest() + ".html"
                creator.set_mainpath(slug)
            else:
                creator.set_mainpath("index.html")

        print(f"ZIM file {self.filename} created.")

if __name__ == "__main__":
    # Test builder
    builder = ZimBuilder("test_output.zim")
    builder.add_article({
        'title': 'Test Article',
        'url': 'http://example.com/1',
        'content': '<h1>Test</h1><p>Content</p>',
        'assets': []
    })
    builder.build()
