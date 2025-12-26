
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import os
import sys
import socket
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
from weather_api import get_weather_service
import security

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
MODULES_DIR = os.path.join(BASE_DIR, "modules")
CONFIG_FILE = os.path.join(BASE_DIR, "module_configs.json")

# Global lock for module updates to prevent race conditions
active_updates = {}
active_updates_lock = threading.Lock()
# Lock for config file access
config_lock = threading.Lock()

def setup_environment():
    """Ensure necessary directories exist."""
    try:
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
        if not os.path.exists(MODULES_DIR):
            os.makedirs(MODULES_DIR)
    except PermissionError:
        print(f"CRITICAL ERROR: Permission denied creating directories in {BASE_DIR}.")
        print(f"Please check file ownership and permissions for the user running this service.")
        sys.exit(1)
    except OSError as e:
        print(f"CRITICAL ERROR: Failed to create directories: {e}")
        sys.exit(1)

def check_port_availability(port):
    """Check if the port is available to bind."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Allow address reuse to prevent false negatives or blocking subsequent binds
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        # Try to bind to all interfaces as the app does
        sock.bind(('0.0.0.0', port))
        return True
    except OSError:
        return False
    finally:
        sock.close()

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def save_metadata(module_path, metadata):
    # Separate private data from public metadata
    public_metadata = metadata.copy()
    private_keys = ['api_key'] # Add other private keys if needed

    with config_lock:
        config = load_config()
        module_name = metadata.get('name')

        if module_name:
            module_config = config.get(module_name, {})
            for key in private_keys:
                if key in public_metadata:
                    module_config[key] = public_metadata.pop(key)
            config[module_name] = module_config
            save_config(config)

    with open(os.path.join(module_path, 'meta.json'), 'w') as f:
        json.dump(public_metadata, f)

def load_metadata(module_path):
    try:
        with open(os.path.join(module_path, 'meta.json'), 'r') as f:
            metadata = json.load(f)

            # Merge with private config
            with config_lock:
                config = load_config()
                module_name = metadata.get('name')
                if module_name and module_name in config:
                    metadata.update(config[module_name])

            return metadata
    except FileNotFoundError:
        return {}

def cleanup_modules():
    """Check for expired modules and delete them."""
    # print("Running cleanup task...") # Too noisy for frequent checks
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

def run_update_task(target_func, module_name, *args):
    """Wrapper to run update task and manage lock."""
    try:
        target_func(*args)
    finally:
        with active_updates_lock:
            if module_name in active_updates:
                del active_updates[module_name]

def check_updates():
    """Check for modules that need to be updated."""
    if not os.path.exists(MODULES_DIR):
        return

    for name in os.listdir(MODULES_DIR):
        module_path = os.path.join(MODULES_DIR, name)
        if not os.path.isdir(module_path):
            continue

        # Check if already updating
        with active_updates_lock:
            if name in active_updates:
                continue

        try:
            metadata = load_metadata(module_path)
            update_interval = metadata.get('update_interval') # in minutes
            last_updated = metadata.get('last_updated')

            if not update_interval:
                continue

            # Determine if update is needed
            # If last_updated is missing, assume it was just created (use created_at) or update now.
            if not last_updated:
                last_updated = metadata.get('created_at', 0)

            # Use timestamps for calculation to avoid timezone/format issues
            next_update_ts = last_updated + (int(update_interval) * 60)

            if datetime.now().timestamp() >= next_update_ts:
                print(f"Module {name} due for update. Updating...")

                # Mark as updating
                with active_updates_lock:
                    active_updates[name] = True

                # Determine type of module and spawn thread
                if 'feed_url' in metadata:
                    category = metadata.get('category', 'News')
                    thread = threading.Thread(
                        target=run_update_task,
                        args=(
                            process_feed,
                            name,
                            metadata['feed_url'],
                            metadata['name'],
                            metadata.get('title', metadata['name']),
                            metadata.get('description', ''),
                            metadata.get('scrape_full_article', False),
                            metadata.get('retention_days', 30),
                            metadata.get('update_interval', 15),
                            category
                        )
                    )
                    thread.start()

                elif 'service' in metadata:
                    try:
                        lat_str, lon_str = metadata['coordinates'].split(',')
                        lat = lat_str.strip()
                        lon = lon_str.strip()
                        category = metadata.get('category', 'Weather')

                        thread = threading.Thread(
                            target=run_update_task,
                            args=(
                                process_weather,
                                name,
                                metadata['service'],
                                metadata.get('api_key', ''),
                                lat,
                                lon,
                                metadata['name'],
                                metadata.get('title', metadata['name']),
                                metadata.get('description', ''),
                                metadata.get('retention_days', 30),
                                metadata.get('update_interval', 15),
                                category
                            )
                        )
                        thread.start()
                    except Exception as e:
                        print(f"Failed to trigger weather update for {name}: {e}")
                        with active_updates_lock:
                            if name in active_updates:
                                del active_updates[name]
        except Exception as e:
            print(f"Error checking updates for {name}: {e}")

def start_scheduler():
    """Background scheduler for cleanup and updates."""
    def run_schedule():
        while True:
            cleanup_modules()
            check_updates()
            # Run every minute to check for updates
            time.sleep(60)

    thread = threading.Thread(target=run_schedule, daemon=True)
    thread.start()

def process_feed(feed_url, module_name, title, description, scrape_full_article, retention_days, update_interval=None, category='News'):
    try:
        print(f"Starting process for {module_name}")

        # Check for existing metadata to preserve creation time
        module_path_existing = os.path.join(MODULES_DIR, module_name)
        existing_metadata = {}
        if os.path.exists(module_path_existing):
             existing_metadata = load_metadata(module_path_existing)

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
        # Merge existing metadata where appropriate
        created_at = existing_metadata.get('created_at', datetime.now().timestamp())

        metadata = {
            'name': module_name,
            'title': title,
            'description': description,
            'created_at': created_at,
            'last_updated': datetime.now().timestamp(),
            'retention_days': retention_days,
            'feed_url': feed_url,
            'scrape_full_article': scrape_full_article,
            'update_interval': update_interval,
            'category': category
        }
        save_metadata(module_path, metadata)

        print(f"Completed process for {module_name}")

    except Exception as e:
        print(f"Error processing {module_name}: {e}")

def process_weather(service_name, api_key, lat, lon, module_name, title, description, retention_days, update_interval=None, category='Weather'):
    try:
        print(f"Starting weather process for {module_name} using {service_name}")

        # Check for existing metadata
        module_path_existing = os.path.join(MODULES_DIR, module_name)
        existing_metadata = {}
        if os.path.exists(module_path_existing):
             existing_metadata = load_metadata(module_path_existing)

        # Preserve API key if not provided in update
        # existing_metadata is initialized to {} above, so this is safe.
        if not api_key and existing_metadata.get('api_key'):
            api_key = existing_metadata.get('api_key')
            print(f"Using existing API key for {module_name}")

        # 1. Fetch Data
        service = get_weather_service(service_name, api_key)
        html_content = service.get_forecast(lat, lon)

        # 2. Build ZIM
        zim_filename = f"{module_name}.zim"
        zim_path = os.path.join(DOWNLOAD_DIR, zim_filename)
        builder = ZimBuilder(zim_path)

        # Create a single article with the weather forecast
        article = {
            'title': title,
            'url': f'http://weather/{module_name}', # Dummy URL
            'content': html_content,
            'assets': []
        }
        builder.add_article(article)
        builder.build()

        # 3. Create Module
        manager = ModuleManager(MODULES_DIR)
        module_path = manager.create_module(module_name, zim_path, title, description)

        # 4. Save Metadata
        created_at = existing_metadata.get('created_at', datetime.now().timestamp())

        metadata = {
            'name': module_name,
            'title': title,
            'description': description,
            'created_at': created_at,
            'last_updated': datetime.now().timestamp(),
            'retention_days': retention_days,
            'service': service_name,
            'coordinates': f"{lat}, {lon}",
            'api_key': api_key, # Saved for auto-updates
            'update_interval': update_interval,
            'category': category
        }
        save_metadata(module_path, metadata)

        print(f"Completed weather process for {module_name}")

    except Exception as e:
        print(f"Error processing weather {module_name}: {e}")

@app.route('/')
def index():
    # List modules
    modules = []
    if os.path.exists(MODULES_DIR):
        for name in os.listdir(MODULES_DIR):
            path = os.path.join(MODULES_DIR, name)
            if os.path.isdir(path):
                metadata = load_metadata(path)

                # Infer category if missing
                category = metadata.get('category')
                if not category:
                    if 'service' in metadata:
                        category = 'Weather'
                    else:
                        category = 'News'

                modules.append({
                    'name': name,
                    'title': metadata.get('title', name),
                    'description': metadata.get('description', 'Generated module'),
                    'path': os.path.abspath(path),
                    'retention_days': metadata.get('retention_days', 'N/A'),
                    'update_interval': metadata.get('update_interval', 'N/A'),
                    'category': category
                })

    # Generate QR Code for App Connection
    local_ip = security.get_local_ip()
    port = int(os.environ.get('PORT', 5002))

    # Use absolute path for cert to ensure it's found regardless of CWD
    cert_path = os.path.join(BASE_DIR, 'cert.pem')
    # If cert doesn't exist yet (first run, creating), we might need to handle that,
    # but the main block creates it before app starts.
    # However, if creating it failed, this might error.
    try:
        fingerprint = security.get_cert_fingerprint(cert_path=cert_path)
    except FileNotFoundError:
        fingerprint = "Certificate not available"

    qr_code_img = security.generate_qr_code_image(local_ip, port, fingerprint)

    # Calculate categories (union of used and default)
    used_categories = set(m['category'] for m in modules if m.get('category'))
    default_categories = {'News', 'Tech', 'Weather', 'Social'}
    all_categories = sorted(list(used_categories.union(default_categories)))

    return render_template('index.html', modules=modules, qr_code_img=qr_code_img, categories=all_categories)

@app.route('/add')
def add_module():
    return render_template('add_module.html')

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
    category = request.form.get('category', 'News')
    scrape_full_article = 'scrape_full_article' in request.form
    try:
        retention_days = int(request.form.get('retention_days', 30))
    except ValueError:
        retention_days = 30

    try:
        update_interval = int(request.form.get('update_interval', 15))
    except ValueError:
        update_interval = 15

    # Run in background to avoid blocking
    thread = threading.Thread(target=process_feed, args=(feed_url, module_name, title, description, scrape_full_article, retention_days, update_interval, category))
    thread.start()

    flash(f"Started generating module '{module_name}'. Check console for progress.")
    return redirect(url_for('index'))

@app.route('/create_weather', methods=['POST'])
def create_weather():
    module_name = request.form['module_name']

    # Sanitize
    module_name = secure_filename(module_name)
    if not module_name:
        flash("Invalid module name.")
        return redirect(url_for('index'))

    title = request.form['title']
    description = request.form.get('description', '')
    category = request.form.get('category', 'Weather')
    service = request.form['service']
    api_key = request.form.get('api_key', '').strip()
    lat = request.form['latitude']
    lon = request.form['longitude']

    try:
        retention_days = int(request.form.get('retention_days', 30))
    except ValueError:
        retention_days = 30

    try:
        update_interval = int(request.form.get('update_interval', 15))
    except ValueError:
        update_interval = 15

    # Run in background
    thread = threading.Thread(target=process_weather, args=(service, api_key, lat, lon, module_name, title, description, retention_days, update_interval, category))
    thread.start()

    flash(f"Started generating weather module '{module_name}'. Check console for progress.")
    return redirect(url_for('index'))

@app.route('/update_module_settings/<module_name>', methods=['POST'])
def update_module_settings(module_name):
    module_name = secure_filename(module_name)
    module_path = os.path.join(MODULES_DIR, module_name)

    if not os.path.exists(module_path) or not os.path.isdir(module_path):
        flash("Module not found.")
        return redirect(url_for('index'))

    try:
        new_interval = int(request.form.get('update_interval', 15))
    except ValueError:
        flash("Invalid interval.")
        return redirect(url_for('index'))

    category = request.form.get('category')

    metadata = load_metadata(module_path)
    metadata['update_interval'] = new_interval
    if category:
        metadata['category'] = category

    save_metadata(module_path, metadata)

    flash(f"Settings for '{module_name}' updated.")
    return redirect(url_for('index'))

@app.route('/delete_module/<module_name>', methods=['POST'])
def delete_module(module_name):
    module_name = secure_filename(module_name)
    module_path = os.path.join(MODULES_DIR, module_name)

    if not os.path.exists(module_path) or not os.path.isdir(module_path):
        flash("Module not found.")
        return redirect(url_for('index'))

    # Remove from active updates if present
    with active_updates_lock:
        if module_name in active_updates:
            del active_updates[module_name]

    try:
        shutil.rmtree(module_path)

        # Cleanup private config
        with config_lock:
            config = load_config()
            if module_name in config:
                del config[module_name]
                save_config(config)

        flash(f"Module '{module_name}' deleted successfully.")
    except Exception as e:
        flash(f"Error deleting module: {e}")

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
    setup_environment()
    start_scheduler()
    port = int(os.environ.get('PORT', 5002))

    if not check_port_availability(port):
        print(f"CRITICAL ERROR: Port {port} is already in use.")
        print("Please stop the existing service or use a different port.")
        time.sleep(2) # Prevent rapid restart loops in systemd
        sys.exit(1)

    # Setup Security
    try:
        local_ip = security.get_local_ip()
        cert_path = os.path.join(BASE_DIR, 'cert.pem')
        key_path = os.path.join(BASE_DIR, 'key.pem')

        try:
            security.check_and_renew_cert(local_ip, cert_path=cert_path, key_path=key_path)
        except PermissionError:
            print(f"CRITICAL ERROR: Permission denied writing certificate files to {BASE_DIR}.")
            print("Please check file ownership and permissions.")
            sys.exit(1)
        except Exception as e:
            print(f"Error checking/renewing certificate: {e}")
            raise e

        # Run with SSL
        print(f"Starting server with SSL on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=False, ssl_context=(cert_path, key_path))
    except SystemExit:
        # Flask/Werkzeug may invoke SystemExit on failure
        sys.exit(1)
    except Exception as e:
        print(f"Failed to start with SSL: {e}")
        print("Falling back to HTTP...")
        try:
            app.run(host='0.0.0.0', port=port, debug=False)
        except SystemExit:
            sys.exit(1)
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to start HTTP server: {e}")
            sys.exit(1)
