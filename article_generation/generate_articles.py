import os
from dotenv import load_dotenv
import requests
import psycopg2
from datetime import datetime
import time
import json

# Load environment variables for secure access
DATABASE_URL = os.getenv("DB_CONNECTION_STRING")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WORDPRESS_CLIENT_ID = os.getenv("WORDPRESS_CLIENT_ID")
WORDPRESS_CLIENT_SECRET = os.getenv("WORDPRESS_CLIENT_SECRET")
WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME")
WORDPRESS_PASSWORD = os.getenv("WORDPRESS_PASSWORD")
# e.g., "your-site.wordpress.com"
WORDPRESS_SITE_URL = os.getenv("WORDPRESS_SITE_URL")

# Generate a WordPress OAuth token


def get_wordpress_token():
    try:
        url = "https://public-api.wordpress.com/oauth2/token"
        data = {
            "client_id": WORDPRESS_CLIENT_ID,
            "client_secret": WORDPRESS_CLIENT_SECRET,
            "username": WORDPRESS_USERNAME,
            "password": WORDPRESS_PASSWORD,
            "grant_type": "password",
        }

        print(f"data: {data}")

        response = requests.post(url, data=data)
        response.raise_for_status()
        token = response.json()["access_token"]
        return token
    except Exception as e:
        print(f"Error generating WordPress token: {e}")
        return None


def fetch_recent_keywords():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        query = """
        SELECT text
        FROM filtered_keywords
        ORDER BY created_at DESC
        LIMIT 10;
        """
        cursor.execute(query)
        keywords = [row[0] for row in cursor.fetchall()]
        conn.close()
        return keywords
    except Exception as e:
        print(f"Error fetching keywords: {e}")
        return []

# Step 2: Generate articles using ChatGPT API


def build_prompt(keyword):
    return (
        f"Generate a fully structured blog post about \"{keyword}\" for a tech and lifestyle site.\n\n"
        "Return your response as a valid JSON object only — no markdown, no explanation.\n\n"
        "The JSON should contain the following keys:\n"
        "  - \"title\": A compelling, SEO-optimized blog title\n"
        "  - \"meta_description\": A ~150-character meta description containing the keyword\n"
        "  - \"slug\": A URL-safe slug derived from the title (e.g. 'quantum-ai-for-gamers')\n"
        "  - \"excerpt\": A short summary or teaser of the article (1 to 2 sentences)\n"
        "  - \"content\": The full HTML blog content (with headings, paragraphs, and internal links described if relevant)\n\n"
        "The tone should be friendly, informative, and technically credible. Format headings using <h2>, <h3> etc. inside the content field.\n"
        "If relevant, suggest 2 to 3 internal links by describing where they would go (but you do not need to insert real URLs).\n\n"
        "Output ONLY a valid JSON object — no prose, no commentary."
    )


def build_openai_request(prompt, max_tokens):
    return {
        "model": "gpt-4",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an experienced SEO content writer for a niche blog. "
                    "Your job is to write compelling, keyword-optimized articles that rank well on Google, "
                    "engage human readers, and follow best SEO practices without keyword stuffing."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 1.0,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.1,
    }


def call_openai_api(data, headers, retries, delay, keyword):
    for attempt in range(1, retries + 1):
        try:
            print(
                f"Attempt {attempt}: Generating article for keyword '{keyword}'...")
            response = requests.post(
                "https://api.openai.com/v1/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            print(f"Successfully generated article for keyword: '{keyword}'")
            return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as http_err:
            code = http_err.response.status_code
            if code == 429:
                print(f"Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            elif code == 500:
                print(f"Server error. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"HTTP error: {http_err}")
                print(f"Response: {http_err.response.content.decode()}")
                break
        except Exception as e:
            print(f"Unexpected error generating article for '{keyword}': {e}")
            break
    print(
        f"Failed to generate article for keyword: '{keyword}' after {retries} attempts.")
    return None


def generate_article(keyword, max_tokens=1500, retries=3, delay=5):
    prompt = build_prompt(keyword)
    data = build_openai_request(prompt, max_tokens)
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    return call_openai_api(data, headers, retries, delay, keyword)


def publish_to_wordpress(title, content, token, excerpt=None, slug=None, status="draft"):
    url = f"https://public-api.wordpress.com/wp/v2/sites/{WORDPRESS_SITE_URL}/posts"

    data = {
        "title": title,
        "content": content,
        "status": status,
    }

    if excerpt:
        data["excerpt"] = excerpt
    if slug:
        data["slug"] = slug

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error publishing article '{title}': {e}")
        return None


def main():
    # Generate WordPress OAuth token
    token = get_wordpress_token()
    if not token:
        print("Failed to obtain WordPress token. Exiting.")
        return

    # Fetch keywords
    keywords = fetch_recent_keywords()
    if not keywords:
        print("No keywords retrieved. Exiting.")
        return

    # Process each keyword
    for keyword in keywords:
        print(f"Processing keyword: {keyword}")
        article = generate_article("quantum computing for gamers")
        try:
            article_data = json.loads(article)
            print("Title:", article_data["title"])
            print("Slug:", article_data["slug"])
            print("Preview:", article_data["meta_description"])
        except json.JSONDecodeError as e:
            print("GPT returned invalid JSON. You may want to retry or clean it up.")
        if article:
            response = publish_to_wordpress(keyword, article, token)
            if response:
                print(f"Published article: {response['link']}")
            else:
                print(f"Failed to publish article for keyword: {keyword}")
        else:
            print(f"Failed to generate article for keyword: {keyword}")


def load_env_from_dotenv():
    # Define the path to the secrets file
    dotenv_path = os.path.abspath("../env_loader/secrets.env")
    print(f"Absolute path to secrets file: {dotenv_path}")

    # Load environment variables from the secrets file
    if load_dotenv(dotenv_path):
        print("Secrets loaded successfully from secrets.env.")
    else:
        print(f"Failed to load secrets.env file from {dotenv_path}")


# Entry point
if __name__ == "__main__":
    load_env_from_dotenv()

    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
    RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")

    print(f"RAPIDAPI_KEY {RAPIDAPI_KEY}")

    DATABASE_URL = os.getenv("DB_CONNECTION_STRING")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    WORDPRESS_CLIENT_ID = os.getenv("WORDPRESS_CLIENT_ID")
    WORDPRESS_CLIENT_SECRET = os.getenv("WORDPRESS_CLIENT_SECRET")
    WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME")
    WORDPRESS_PASSWORD = os.getenv("WORDPRESS_PASSWORD")
    # e.g., "your-site.wordpress.com"
    WORDPRESS_SITE_URL = os.getenv("WORDPRESS_SITE_URL")

    main()
