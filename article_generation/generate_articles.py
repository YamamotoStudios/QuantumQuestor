import os
from dotenv import load_dotenv
import requests
import psycopg2
from datetime import datetime
import time
import json
import re

# Load environment variables for secure access
DATABASE_URL = os.getenv("DB_CONNECTION_STRING")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME")
WORDPRESS_PASSWORD = os.getenv("WORDPRESS_PASSWORD")
# e.g., "your-site.wordpress.com"
WORDPRESS_SITE_URL = os.getenv("WORDPRESS_SITE_URL")

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
        f'Generate a fully structured blog post about keyword:"{keyword}" for a tech and lifestyle site.\n\n'
        "IMPORTANT:\n"
        "- Do NOT include Markdown, explanations, or text outside the JSON.\n"
        "- Output MUST be a single valid JSON object only, properly formatted and escaped.\n"
        "- Warning: Ending early or skipping sections will result in rejection.\n"
        "- Respond with raw JSON only — no markdown.\n"
        "- If any keywords are of a specific year or date, it must instead be assumed its this year instead, to give an up to date and relevant article.  If its concerning older news, then its an incomplete article.\n"
        "- There must be at least 2 links to external resources.\n"
        "Requirements:\n"
        "- Length: You must write at least 1500 words (not characters, it would be many, many more characters) of content. If this condition is not met, the task is incomplete. Do not stop early or summarize. Each major section (under <h2>) must include at least 2–3 paragraphs. Include examples, comparisons, and in-depth explanation in each part.\n"
        "- If the word count is under 1500, continue generating more content as a follow-up. Do not conclude the article until the total exceeds 1500 words. \n"
        "- Cover both informational (explain concepts, how-tos) and transactional (product/service recommendations, CTAs) aspects of the topic.\n"
        "- Structure: Use logical, creative HTML structure with <h2>, <h3>, <p>, <ul>, <ol> as needed. No fixed template required.\n"
        "- Tone: Friendly, informative, and technically credible. Avoid first-person unless appropriate.\n"
        "- SEO: Optimize for search. Include target keyword naturally in:\n"
        "    • title\n"
        "    • meta_description (~150 characters)\n"
        "    • content headings and early paragraphs\n"
        "- Use semantic keywords and related terms to improve topical coverage.\n"
        "- Slug: Derive from title (lowercase, hyphens, no special characters).\n"
        "- Excerpt: Write a 1–2 sentence teaser.\n"
        # "- Internal Links: Suggest 2–3 contextual internal links using descriptions like [Link: Guide to Quantum PCs].\n"
        "- Structured Data: Optionally include JSON-LD inside <script type=\"application/ld+json\"> blocks for Article or FAQ schema. It must be valid JSON-LD and must not appear as visible text on the page — embed it properly within the HTML content.\n"
        "- Output only valid JSON with the following keys:\n"
        "    • \"title\"\n"
        "    • \"meta_description\"\n"
        "    • \"slug\"\n"
        "    • \"excerpt\"\n"
        "    • \"content\" – full HTML, with internal link placeholders and optional <script> JSON-LD schema blocks embedded (not visible text).\n\n"

    )


def build_openai_request(prompt, max_tokens):
    return {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": (
                    "IMPORTANT: you like to write long, indepth, detailed articles, going into depth, and only summarising in additiona to long description, not instead of. "
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


def generate_article(keyword, max_tokens=7000, retries=3, delay=5):
    prompt = build_prompt(keyword)
    data = build_openai_request(prompt, max_tokens)
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    return call_openai_api(data, headers, retries, delay, keyword)


def publish_to_wordpress(title, content, site_url, excerpt=None, slug=None, status="draft"):
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
                token=token,
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
