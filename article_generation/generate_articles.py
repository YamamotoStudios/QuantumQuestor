import os
from dotenv import load_dotenv
import requests
import psycopg2
from datetime import datetime
from env_loader import load_env
import time

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

# Step 1: Fetch the latest 10 keywords from the database


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


def generate_article(keyword, max_tokens=1500, retries=3, delay=5):
    """
    Generate an article using the OpenAI API with retries and rate-limiting.

    Args:
        keyword (str): The keyword for the article.
        max_tokens (int): Maximum tokens for the generated content.
        retries (int): Number of retry attempts for handling failures.
        delay (int): Initial delay (in seconds) between retries.

    Returns:
        str or None: The generated article text, or None if failed.
    """
    prompt = f"Write a detailed article about '{keyword}'. Include an introduction, main content, and conclusion."
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
    }

    for attempt in range(1, retries + 1):
        try:
            print(
                f"Attempt {attempt}: Generating article for keyword '{keyword}'...")
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            print(f"Successfully generated article for keyword: '{keyword}'")
            return response.json()["choices"][0]["message"]["content"]

        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 429:  # Rate limit exceeded
                print(f"Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                continue
            elif http_err.response.status_code == 500:  # Server error
                print(f"Server error. Retrying in {delay} seconds...")
                time.sleep(delay)
                continue
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

# Step 3: Publish articles to WordPress


def publish_to_wordpress(title, content, token):
    url = f"https://public-api.wordpress.com/wp/v2/sites/{WORDPRESS_SITE_URL}/posts"
    data = {
        "title": title,
        "content": content,
        "status": "draft",
    }
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

# Main function


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
        article = generate_article(keyword)
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

    DATABASE_URL = os.getenv("DB_CONNECTION_STRING")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    WORDPRESS_CLIENT_ID = os.getenv("WORDPRESS_CLIENT_ID")
    WORDPRESS_CLIENT_SECRET = os.getenv("WORDPRESS_CLIENT_SECRET")
    WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME")
    WORDPRESS_PASSWORD = os.getenv("WORDPRESS_PASSWORD")
    # e.g., "your-site.wordpress.com"
    WORDPRESS_SITE_URL = os.getenv("WORDPRESS_SITE_URL")

    main()
