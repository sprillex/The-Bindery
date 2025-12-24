
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import os
import threading
import json
import shutil
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Response
from libzim.reader import Archive
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

def save_metadata(module_path, metadata):
    with open(os.path.join(module_path, 'meta.json'), 'w') as f:
        json.dump(metadata, f)

def load_metadata(module_path):
    try:
        with open(os.path.join(module_path, 'meta.json'), 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def cleanup_modules():
    """Check for expired modules and delete them."""
    print("Running cleanup task...")
    if not os.path.exists(MODULES_DIR):
        return

    for name in os.listdir(MODULES_DIR):
        module_path = os.path.join(MODULES_DIR, name)
        if os.path.isdir(module_path):
            metadata = load_metadata(module_path)
            created_at_ts = metadata.get('created_at')
            retention_days = metadata.get('retention_days')

            if created_at_ts and retention_days:
                created_at = datetime.fromtimestamp(created_at_ts)
                expiration_date = created_at + timedelta(days=retention_days)

                if datetime.now() > expiration_date:
                    print(f"Module {name} expired. Deleting...")
                    try:
                        shutil.rmtree(module_path)
                        print(f"Deleted expired module: {name}")
                    except Exception as e:
                        print(f"Failed to delete {name}: {e}")

def start_scheduler():
    """Simple background scheduler for cleanup."""
    def run_schedule():
        while True:
            cleanup_modules()
            # Run every hour
            time.sleep(3600)

    thread = threading.Thread(target=run_schedule, daemon=True)
    thread.start()

def process_feed(feed_url, module_name, title, description, scrape_full_article, retention_days):
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
        module_path = manager.create_module(module_name, zim_path, title, description)

        # 4. Save Metadata
        metadata = {
            'name': module_name,
            'title': title,
            'description': description,
            'created_at': datetime.now().timestamp(),
            'retention_days': retention_days,
            'feed_url': feed_url
        }
        save_metadata(module_path, metadata)

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
                metadata = load_metadata(path)
                modules.append({
                    'name': name,
                    'title': metadata.get('title', name),
                    'description': metadata.get('description', 'Generated module'),
                    'path': os.path.abspath(path),
                    'retention_days': metadata.get('retention_days', 'N/A')
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
    try:
        retention_days = int(request.form.get('retention_days', 30))
    except ValueError:
        retention_days = 30

    # Run in background to avoid blocking
    thread = threading.Thread(target=process_feed, args=(feed_url, module_name, title, description, scrape_full_article, retention_days))
    thread.start()

    flash(f"Started generating module '{module_name}'. Check console for progress.")
    return redirect(url_for('index'))

@app.route('/modules/<path:filename>')
def serve_module(filename):
    return send_from_directory(MODULES_DIR, filename)

@app.route('/preview/<module_name>/')
@app.route('/preview/<module_name>/<path:filename>')
def preview_zim(module_name, filename=None):
    # secure_filename checks
    module_name = secure_filename(module_name)
    zim_path = os.path.join(MODULES_DIR, module_name, f"{module_name}.zim")

    if not os.path.exists(zim_path):
        return "Module not found", 404

    try:
        archive = Archive(zim_path)
    except Exception as e:
        return f"Error opening ZIM: {e}", 500

    if filename is None:
        # Redirect to main page
        if archive.has_main_entry:
            entry = archive.main_entry
            while entry.is_redirect:
                entry = entry.get_redirect_entry()
            main_path = entry.path
            return redirect(url_for('preview_zim', module_name=module_name, filename=main_path))
        return "No main page found in ZIM", 404

    try:
        entry = archive.get_entry_by_path(filename)
        while entry.is_redirect:
            entry = entry.get_redirect_entry()

        item = entry.get_item()
        return Response(bytes(item.content), mimetype=item.mimetype)
    except KeyError:
        return "File not found in ZIM", 404

if __name__ == '__main__':
    start_scheduler()
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=False)
