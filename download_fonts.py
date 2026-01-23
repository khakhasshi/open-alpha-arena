import re
import os
import requests

CSS_FILE = "frontend/public/vendor/css/google-fonts.css"
FONTS_DIR = "frontend/public/vendor/fonts"

os.makedirs(FONTS_DIR, exist_ok=True)

with open(CSS_FILE, "r") as f:
    css_content = f.read()

# Find all URLs
# Pattern for url(...)
urls = re.findall(r'url\((.*?)\)', css_content)

new_css_content = css_content

print(f"Found {len(urls)} font files to download...")

for i, url in enumerate(urls):
    url = url.strip().strip("'").strip('"')
    filename = url.split("/")[-1]
    local_path = os.path.join(FONTS_DIR, filename)
    
    # Download
    print(f"Downloading {filename}...")
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(r.content)
            
        # Replace in CSS
        # We need to replace the exact URL string in the CSS with the relative path
        # from css/ file to fonts/ file: ../fonts/filename
        new_css_content = new_css_content.replace(url, f"../fonts/{filename}")
        
    except Exception as e:
        print(f"Failed to download {url}: {e}")

with open(CSS_FILE, "w") as f:
    f.write(new_css_content)

print("Done. CSS updated.")
