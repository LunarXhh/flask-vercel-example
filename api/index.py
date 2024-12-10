from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import os
import re
import urllib.parse
import time
import random
import base64
from io import BytesIO
from urllib.parse import urlparse
import html2text

app = Flask(__name__)

def search_images(query, num_images=5):
    # Headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
    }

    # Format the query for URL
    formatted_query = urllib.parse.quote(query)

    # Google Images URL
    url = f"https://www.google.com/search?q={formatted_query}&tbm=isch&safe=active"

    try:
        # Get the HTML content
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Find all image URLs using regex
        image_urls = re.findall(r'https?://[^"\']*?(?:jpg|jpeg|png|gif)', response.text)

        # Remove duplicates while preserving order
        image_urls = list(dict.fromkeys(image_urls))

        # Store results
        results = []
        downloaded = 0

        for img_url in image_urls:
            if downloaded >= num_images:
                break

            try:
                # Skip small thumbnails and icons
                if 'gstatic.com' in img_url or 'google.com' in img_url:
                    continue

                # Download image
                img_response = requests.get(img_url, headers=headers, timeout=10)
                img_response.raise_for_status()

                # Check if the response is actually an image
                content_type = img_response.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    continue

                # Convert image to base64
                image_base64 = base64.b64encode(img_response.content).decode('utf-8')

                # Add to results
                results.append({
                    'image_url': img_url,
                    'base64_data': f"data:{content_type};base64,{image_base64}"
                })

                downloaded += 1

                # Add a random delay between downloads
                time.sleep(random.uniform(0.5, 1))

            except Exception as e:
                print(f"Error downloading image: {str(e)}")
                continue

        return results

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return []

@app.route('/search_images', methods=['GET'])
def api_search_images():
    try:
        # Get query parameters
        query = request.args.get('query', '')
        num_images = int(request.args.get('num_images', 5))

        if not query:
            return jsonify({'error': 'Query parameter is required'}), 400

        if num_images < 1 or num_images > 20:
            return jsonify({'error': 'Number of images must be between 1 and 20'}), 400

        # Search for images
        results = search_images(query, num_images)

        return jsonify({
            'success': True,
            'query': query,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_domain(url):
    """Extract domain from URL"""
    parsed_uri = urlparse(url)
    return parsed_uri.netloc

def clean_text(text):
    """Clean scraped text"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters
    text = re.sub(r'[^\w\s.,!?-]', '', text)
    return text.strip()

def scrape_website(url, headers):
    """Scrape content from a single website"""
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'iframe']):
            element.decompose()

        # Convert HTML to text
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        text = h.handle(str(soup))

        # Clean the text
        text = clean_text(text)

        # Get meta description
        meta_desc = ''
        meta_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if meta_tag:
            meta_desc = meta_tag.get('content', '')

        # Get title
        title = soup.title.string if soup.title else ''

        return {
            'title': clean_text(title),
            'meta_description': clean_text(meta_desc),
            'content': text[:1000],  # Limit content length
            'url': url
        }

    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")
        return None

def search_and_scrape(query, num_results=5):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
    }

    # Format the query for URL
    formatted_query = urllib.parse.quote(query)

    # Google Search URL
    url = f"https://www.google.com/search?q={formatted_query}&num={num_results}"

    try:
        # Get Google search results
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all search result divs
        search_results = []
        result_divs = soup.find_all('div', class_='g')

        for div in result_divs:
            # Find the link
            link = div.find('a')
            if not link:
                continue

            href = link.get('href', '')

            # Skip if not a valid URL or if it's a Google-related URL
            if not href.startswith('http') or 'google.' in href:
                continue

            # Add random delay between requests
            time.sleep(random.uniform(1, 2))

            # Scrape the website
            site_data = scrape_website(href, headers)
            if site_data:
                search_results.append(site_data)

            if len(search_results) >= num_results:
                break

        return search_results

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return []

@app.route('/scrape_sites', methods=['GET'])
def api_scrape_sites():
    try:
        # Get query parameters
        query = request.args.get('query', '')
        num_results = int(request.args.get('num_results', 5))

        if not query:
            return jsonify({'error': 'Query parameter is required'}), 400

        if num_results < 1 or num_results > 10:
            return jsonify({'error': 'Number of results must be between 1 and 10'}), 400

        # Search and scrape sites
        results = search_and_scrape(query, num_results)

        return jsonify({
            'success': True,
            'query': query,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)







