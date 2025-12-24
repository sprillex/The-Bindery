
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import os
import threading
from werkzeug.utils import secure_filename
from scraper import Scraper
from zim_builder import ZimBuilder
from module_manager import ModuleManager
import time

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configuration
DOWNLOAD_DIR = "downloads"
MODULES_DIR = "modules"

# Ensure directories exist
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
if not os.path.exists(MODULES_DIR):
    os.makedirs(MODULES_DIR)

def process_feed(feed_url, module_name, title, description, scrape_full_article):
    try:
        print(f"Starting process for {module_name}")

        # 1. Scrape
        scraper = Scraper(os.path.join(DOWNLOAD_DIR, module_name))
        articles = scraper.scrape_feed(feed_url, scrape_full_article=scrape_full_article)

        if not articles:
            print("No articles found.")
            return

        # 2. Build ZIM
        zim_filename = f"{module_name}.zim"
        zim_path = os.path.join(DOWNLOAD_DIR, zim_filename)
        builder = ZimBuilder(zim_path)
        for article in articles:
            builder.add_article(article)
        builder.build()

        # 3. Create Module
        manager = ModuleManager(MODULES_DIR)
        manager.create_module(module_name, zim_path, title, description)

        print(f"Completed process for {module_name}")

    except Exception as e:
        print(f"Error processing {module_name}: {e}")

@app.route('/')
def index():
    # List modules
    modules = []
    if os.path.exists(MODULES_DIR):
        for name in os.listdir(MODULES_DIR):
            path = os.path.join(MODULES_DIR, name)
            if os.path.isdir(path):
                # Try to read metadata from rachel-index.php or just use folder name
                modules.append({
                    'name': name,
                    'title': name, # Placeholder
                    'description': 'Generated module',
                    'path': os.path.abspath(path)
                })
    return render_template('index.html', modules=modules)

@app.route('/create', methods=['POST'])
def create():
    feed_url = request.form['feed_url']
    module_name = request.form['module_name']

    # Sanitize module name to prevent path traversal
    module_name = secure_filename(module_name)
    if not module_name:
        flash("Invalid module name.")
        return redirect(url_for('index'))

    title = request.form['title']
    description = request.form.get('description', '')
    scrape_full_article = 'scrape_full_article' in request.form

    # Run in background to avoid blocking
    thread = threading.Thread(target=process_feed, args=(feed_url, module_name, title, description, scrape_full_article))
    thread.start()

    flash(f"Started generating module '{module_name}'. Check console for progress.")
    return redirect(url_for('index'))

@app.route('/modules/<path:filename>')
def serve_module(filename):
    return send_from_directory(MODULES_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
