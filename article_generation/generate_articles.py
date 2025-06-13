import os
from dotenv import load_dotenv
import requests
import psycopg2
from datetime import datetime
import time
import json
import re
import requests
from requests.auth import HTTPBasicAuth

# Load environment variables for secure access
DATABASE_URL = os.getenv("DB_CONNECTION_STRING")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME")
WORDPRESS_PASSWORD = os.getenv("WORDPRESS_PASSWORD")

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
        f'Write a long-form, blog-style article about keyword: "{keyword}" for a tech and lifestyle site that values expert depth and a conversational tone.\n\n'
        "=== CONTENT GOALS ===\n"
        "- Write at least **1,800–2,000 words** of in-depth content, which according to the Flesch-Kincaid scale is at least easy to read. Aim to truly educate, engage, or persuade a curious reader — not just summarise, in fact avoid summarising.\n"
        "- Use a **natural, human tone**. Avoid robotic phrasing. Write like an experienced writer would: clear, informative, occasionally witty.\n"
        "- Go beyond surface-level facts. Include:\n"
        "  • Examples or case studies\n"
        "  • First-hand style insights (e.g. ‘One thing I’ve found...’)\n"
        "  • Pros, cons, comparisons, and counterpoints\n"
        "  • References to real tools, platforms, events, or concepts\n"
        "- Structure the post logically using <h2> and <h3> headers. Use <ul>, <ol>, and <p> for clarity.\n"
        "- DO NOT stop until the article hits a **minimum** of 1,800 words. If needed, keep expanding thoughtfully until that’s achieved.\n"
        "=== SEO + STRUCTURE ===\n"
        "- Include these JSON keys:\n"
        "    • \"title\"\n"
        "    • \"meta_description\" (~150 characters)\n"
        "    • \"slug\" (SEO-friendly)\n"
        "    • \"excerpt\" (1–2 sentence teaser)\n"
        "    • \"content\" (full HTML of the article)\n"
        "- Use the keyword naturally in the **title**, **intro**, and **headings**. Avoid keyword stuffing.\n"
        "- Include **1–2 external citations** (real links to a real website).\n"
        "- MUST Include **<script type=\"application/ld+json\">** block with valid Article schema at the end of content.\n"
        "=== IMPORTANT STYLE NOTES ===\n"
        "- Avoid all AI tropes (e.g. 'In today’s fast-paced world…')\n"
        "- Avoid repeating phrases, overuse of transition words, or empty conclusions.\n"
        "- Focus on delivering original, **thought-provoking** content.\n"
        "- Output must be a single valid JSON object. DO NOT include Markdown or notes outside the JSON.\n"
    )


def build_openai_request(prompt, max_tokens):
    return {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": (
                    "IMPORTANT: you like to write long, indepth, conversational, and detailed articles, going into depth, but summarising and concluding in the final paragraph. "
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
        "stop": ["###", "\n\n##"]  # helps catch overly long digressions
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


def generate_article(keyword, max_tokens=7000, retries=3, delay=5):
    prompt = build_prompt(keyword)
    data = build_openai_request(prompt, max_tokens)
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    return call_openai_api(data, headers, retries, delay, keyword)


def publish_to_wordpress(title, content, excerpt=None, slug=None, status="draft"):
    url = "https://quantumquestor.com/wp-json/wp/v2/posts"

    data = {
        "title": title,
        "content": content,
        "status": status,
    }

    if excerpt:
        data["excerpt"] = excerpt
    if slug:
        data["slug"] = slug

    try:
        response = requests.post(
            url,
            json=data,
            auth=HTTPBasicAuth(WORDPRESS_USERNAME, WORDPRESS_PASSWORD),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error publishing article '{title}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Server response: {e.response.text}")
        return None


def main():
    # Fetch keywords
    keywords = fetch_recent_keywords()
    if not keywords:
        print("No keywords retrieved. Exiting.")
        return

    # Process each keyword
    for keyword in keywords:
        print(f"Processing keyword: {keyword}")
        article = generate_article(keyword)
        try:
            if article.strip().startswith("```json"):
                article = re.sub(r"^```json\s*|\s*```$", "", article.strip())
            
            article_data = json.loads(article)
            print("Title:", article_data["title"])
            print("Slug:", article_data["slug"])
            print("Preview:", article_data["meta_description"])
        except json.JSONDecodeError as e:
            print(f"GPT returned invalid JSON. You may want to retry or clean it up. {article}")
        if article_data:
            response = publish_to_wordpress(
                title=article_data["title"],
                content=article_data["content"],
                excerpt=article_data.get("excerpt"),
                slug=article_data.get("slug")
            )
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
