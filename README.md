# RACHEL/OER2Go Module Creator

This project is a tool to create offline content modules compatible with [RACHEL](https://worldpossible.org/rachel) (Remote Area Community Hotspot for Education and Learning) and OER2Go devices.

It allows you to scrape content from RSS feeds, convert it into a [ZIM file](https://wiki.openzim.org/wiki/ZIM_file_format) (using `libzim`), and package it into the standard RACHEL module format.

## Features

-   **RSS Scraping**: Fetches articles and images from any standard RSS feed.
-   **ZIM Creation**: Generates compressed ZIM archives suitable for offline viewing via Kiwix (standard on RACHEL).
-   **RACHEL Formatting**: Automatically creates the directory structure and `rachel-index.php` required for the module to appear on the RACHEL homepage.
-   **Web Interface**: Simple web UI to manage and create modules.

## Installation

### Prerequisites

-   Python 3.8 or higher
-   `pip` (Python package manager)

### Steps

1.  Clone this repository:
    ```bash
    git clone https://github.com/sprillex/The-Bindery
    cd The-Bindery
    ```

2.  Set up a virtual environment (Recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

    *Note: This installs `libzim`, `feedparser`, `beautifulsoup4`, `flask`, and others.*

## Usage

1.  Activate the virtual environment (if not already active):
    ```bash
    source venv/bin/activate
    ```

2.  Start the web server:
    ```bash
    python src/server.py
    ```

    *By default, the server runs on port 5002. To use a different port, set the `PORT` environment variable:*
    ```bash
    PORT=8080 python src/server.py
    ```

2.  Open your web browser and navigate to:
    ```
    http://localhost:5002
    ```

    *To access from another device on the network, replace `localhost` with the device's IP address (e.g., `http://192.168.1.100:5002`).*

3.  **Create a Module**:
    -   **RSS Feed URL**: Enter the URL of the RSS feed you want to scrape (e.g., `http://feeds.bbci.co.uk/news/rss.xml`).
    -   **Module Directory Name**: A unique, safe name for the folder (e.g., `bbc_news`). Use lowercase letters, numbers, and underscores only.
    -   **Module Title**: The display title for the module on the RACHEL homepage.
    -   **Description**: A short description of the content.

4.  Click **Generate Module**. The process runs in the background. Depending on the size of the feed and number of images, this may take several minutes.

5.  **Download**: Once finished, the module will appear in the "Existing Modules" list. You can download the ZIM file directly or access the full module structure in the `modules/` directory on the server.

## Integration with RACHEL

To install the generated module onto a RACHEL device (e.g., Raspberry Pi):

1.  Locate the generated module folder in the `modules/` directory of this project (e.g., `modules/bbc_news`).
2.  Copy the entire folder (e.g., `bbc_news`) to the RACHEL modules directory on your device.
    -   Typical path on RACHEL-Pi: `/var/www/modules/`
3.  Ensure permissions are correct (usually `www-data` or `root` ownership depending on setup).
4.  **Restart Kiwix**:
    -   RACHEL uses Kiwix to serve ZIM files. You may need to restart the Kiwix service or reboot the device for the new ZIM file to be detected and indexed.
    -   Common command: `sudo /var/kiwix/bin/rachel-kiwix-start.pl` or simply reboot.
5.  Refresh the RACHEL homepage. Your new module should appear in the list.

## Directory Structure

```
.
├── src/
│   ├── server.py          # Main Flask application
│   ├── scraper.py         # RSS scraping logic
│   ├── zim_builder.py     # ZIM file generation logic
│   ├── module_manager.py  # RACHEL directory structure helper
│   └── templates/         # HTML templates
├── modules/               # Generated RACHEL modules (output)
├── downloads/             # Temporary download cache
└── requirements.txt       # Dependencies
```

## Troubleshooting

-   **Scraping Fails**: Ensure the RSS feed URL is correct and the server has internet access. Some sites may block scrapers; the scraper uses a standard User-Agent.
-   **ZIM Error**: If `libzim` fails to install, ensure you have a compatible OS (Linux/macOS recommended). Windows support for `libzim` wheels can vary.

## Verification

To verify that the application is working correctly:

1.  **Check Server Status**: Ensure the script is running without errors in the terminal. You should see output indicating the server is running on `http://0.0.0.0:5002`.
2.  **Access UI**: Open a browser and go to `http://localhost:5002`. You should see the "RACHEL Module Creator" form.
3.  **Test Module Creation**:
    -   Enter a valid RSS URL (e.g., `http://feeds.bbci.co.uk/news/rss.xml`).
    -   Enter a simple name (e.g., `test`).
    -   Click "Generate Module".
    -   Wait for the "Completed process for test" message in the terminal.
4.  **Verify Output**:
    -   Refresh the page. The new module should appear in the list.
    -   Click **Preview Content**. A new tab should open displaying the scraped content.
    -   Click **Download ZIM**. The file should download successfully.
