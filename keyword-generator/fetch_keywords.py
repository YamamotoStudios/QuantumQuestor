import psycopg2
from datetime import datetime, timedelta
import json
from sentence_transformers import SentenceTransformer, util
import time
from concurrent.futures import ThreadPoolExecutor
import os

# API and configuration
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
CACHE_EXPIRATION_HOURS = 24

# Database connection details
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")

# Load the SentenceTransformer model
print("Loading SentenceTransformer model...")
start_time = time.time()
model = SentenceTransformer("all-MiniLM-L6-v2")
print(f"Model loaded in {time.time() - start_time:.2f} seconds.")

# Helper functions


def fetch_keywords_from_api(endpoint, params):
    url = f"https://{RAPIDAPI_HOST}/{endpoint}/"
    headers = {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            data = [data]
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {endpoint}: {e}")
        return []


def cache_raw_keywords(conn, raw_keywords):
    """Cache raw keywords in the database."""
    with conn.cursor() as cur:
        for keyword in raw_keywords:
            cur.execute("""
                INSERT INTO raw_keywords (text, volume, competition_level, trend, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (text) DO NOTHING
            """, (keyword["text"], keyword.get("volume", 0),
                  keyword.get("competition_level", ""), keyword.get("trend", 0.0), datetime.utcnow()))
        conn.commit()


def fetch_cached_keywords(conn):
    """Fetch cached raw keywords that haven't expired."""
    expiration_time = datetime.utcnow() - timedelta(hours=CACHE_EXPIRATION_HOURS)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT text, volume, competition_level, trend, created_at
            FROM raw_keywords
            WHERE created_at >= %s
        """, (expiration_time,))
        return [
            {"text": row[0], "volume": row[1],
                "competition_level": row[2], "trend": row[3]}
            for row in cur.fetchall()
        ]


def save_filtered_keywords(conn, filtered_keywords):
    """Save filtered keywords to the database."""
    with conn.cursor() as cur:
        for keyword in filtered_keywords:
            cur.execute("""
                INSERT INTO filtered_keywords (text, similarity, score, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (text) DO NOTHING
            """, (keyword["text"], keyword["similarity"], keyword["score"], datetime.utcnow()))
        conn.commit()


def fetch_and_analyze_keywords():
    # Connect to the database
    conn = psycopg2.connect(DB_CONNECTION_STRING)

    try:
        # Check for cached data
        cached_keywords = fetch_cached_keywords(conn)
        if cached_keywords:
            print("Using cached keywords...")
            combined_data = cached_keywords
        else:
            combined_data = []
            print("Fetching data concurrently for all seed keywords...")

            # Fetch seed keywords from the database
            with conn.cursor() as cur:
                cur.execute("SELECT keyword FROM seed_keywords")
                seed_keywords = [row[0] for row in cur.fetchall()]

            def fetch_data_for_seed(seed):
                try:
                    keysuggest_data = fetch_keywords_from_api(
                        "keysuggest", {"keyword": seed, "location": "GB", "lang": "en"})
                    globalkey_data = fetch_keywords_from_api(
                        "globalkey", {"keyword": seed, "lang": "en"})
                    topkeys_data = fetch_keywords_from_api(
                        "topkeys", {"keyword": seed, "location": "GB", "lang": "en"})

                    combined_data = []
                    for data in (keysuggest_data, globalkey_data, topkeys_data):
                        if isinstance(data, list):
                            combined_data.extend(data)
                        elif isinstance(data, dict):
                            combined_data.append(data)

                    print(f"Success fetching data for seed '{seed}'")
                    return combined_data
                except Exception as e:
                    print(f"Error fetching data for seed '{seed}': {e}")
                    return []

            with ThreadPoolExecutor() as executor:
                combined_data_lists = list(executor.map(
                    fetch_data_for_seed, seed_keywords))
                combined_data = [
                    item for sublist in combined_data_lists for item in sublist
                ]

            print(f"Fetched {len(combined_data)} total keywords.")
            cache_raw_keywords(conn, combined_data)

        # Filter and process data
        filtered_data = [
            item for item in combined_data
            if (
                item.get("volume", 0) > 100 and
                item.get("competition_level", "").lower() in ["low", "medium"] and
                item.get("trend", 0) >= 0 and
                len(item.get("text", "").split()) >= 2
            )
        ]
        print(f"{len(filtered_data)} keywords passed initial filters.")

        if not filtered_data:
            print("No keywords passed the filters. Adjust thresholds or input data.")
            return

        # Semantic similarity analysis
        texts = [item["text"] for item in filtered_data]
        print("Starting semantic similarity analysis...")
        similarities = calculate_similarity_batch(seed_keywords, texts)

        # Add similarity scores and calculate final scores
        max_volume = max(item["volume"] for item in filtered_data)
        for item, similarity in zip(filtered_data, similarities):
            volume = item["volume"]
            trend = item["trend"]
            item["similarity"] = similarity
            item["score"] = 0.7 * similarity + 0.2 * \
                trend + 0.1 * (volume / max_volume)

        # Save results to the database
        save_filtered_keywords(conn, filtered_data)
        print("Filtered keywords saved to the database.")

    finally:
        conn.close()


# Run the script
if __name__ == "__main__":
    fetch_and_analyze_keywords()
