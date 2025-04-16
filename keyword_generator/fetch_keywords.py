from dotenv import load_dotenv
import requests
from collections import Counter
import os
from concurrent.futures import ThreadPoolExecutor
import time
from sklearn.cluster import AgglomerativeClustering
from sentence_transformers import SentenceTransformer, util
import json
from datetime import datetime, timedelta
import psycopg2

# API and configuration
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
CACHE_EXPIRATION_HOURS = 24
OUTPUT_FILE = "keywords.json"

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


def calculate_similarity_batch(seed_keywords, texts):
    seed_embeddings = model.encode(seed_keywords, convert_to_tensor=True)
    text_embeddings = model.encode(texts, convert_to_tensor=True)
    return util.cos_sim(seed_embeddings, text_embeddings).max(dim=0).values.cpu().tolist()


def adjust_score_for_repetition(keywords):
    keyword_texts = [kw["text"].lower() for kw in keywords]
    repetition_counts = Counter(keyword_texts)
    for keyword in keywords:
        repetitions = repetition_counts[keyword["text"].lower()]
        if repetitions > 1:
            penalty = 0.1 * (repetitions - 1)
            keyword["score"] -= penalty
            keyword["score"] = max(keyword["score"], 0)
    return keywords


def cluster_keywords(keywords, num_clusters=10):
    texts = [kw["text"] for kw in keywords]
    embeddings = model.encode(texts)
    clustering = AgglomerativeClustering(
        n_clusters=num_clusters, metric="euclidean", linkage="ward"
    )
    cluster_labels = clustering.fit_predict(embeddings)
    clusters = {}
    for idx, label in enumerate(cluster_labels):
        clusters.setdefault(label, []).append(keywords[idx])
    return clusters


def select_from_clusters(clusters):
    final_keywords = []
    for cluster_id, cluster_keywords in clusters.items():
        best_keyword = max(cluster_keywords, key=lambda x: x["score"])
        final_keywords.append(best_keyword)
    return final_keywords


def fetch_cached_keywords(conn):
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
    with conn.cursor() as cur:
        for keyword in filtered_keywords:
            cur.execute("""
                INSERT INTO filtered_keywords (text, similarity, score, created_at)
                VALUES (%s, %s, %s, %s)
            """, (keyword["text"], keyword["similarity"], keyword["score"], datetime.utcnow()))
        conn.commit()

def fetch_blacklist(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT term FROM blacklist")
        return set(row[0].lower() for row in cur.fetchall())

def insert_into_blacklist(conn, keywords):
    with conn.cursor() as cur:
        for kw in keywords:
            cur.execute("""
                INSERT INTO blacklist (term)
                VALUES (%s)
                ON CONFLICT (term) DO NOTHING
            """, (kw.lower(),))
        conn.commit()

def fetch_and_analyze_keywords():
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    try:
        # Fetch existing blacklist
        blacklist = fetch_blacklist(conn)

        cached_keywords = fetch_cached_keywords(conn)
        if cached_keywords:
            print("Using cached keywords...")
            combined_data = cached_keywords
        else:
            combined_data = []
            print("Fetching data concurrently for all seed keywords...")
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
                    return keysuggest_data + globalkey_data + topkeys_data
                except Exception as e:
                    print(f"Error fetching data for seed '{seed}': {e}")
                    return []

            with ThreadPoolExecutor() as executor:
                combined_data_lists = list(executor.map(
                    fetch_data_for_seed, seed_keywords))
                combined_data = [
                    item for sublist in combined_data_lists for item in sublist]

        # Filter out blacklisted terms
        pre_filter_count = len(combined_data)
        filtered_data = []
        for item in combined_data:
            text = item.get("text", "").strip().lower()
            if (
                text not in blacklist and
                item.get("volume", 0) > 100 and
                item.get("competition_level", "").lower() in ["low", "medium"] and
                item.get("trend", 0) >= 0 and
                len(text.split()) >= 2
            ):
                filtered_data.append(item)

        print(f"{len(filtered_data)} keywords passed initial filters.")
        print(f"{pre_filter_count - len(filtered_data)} keywords ignored due to blacklist or filter failure.")

        if not filtered_data:
            print("No keywords passed the filters.")
            return

        texts = [item["text"] for item in filtered_data]
        print("Starting semantic similarity analysis...")
        similarities = calculate_similarity_batch(seed_keywords, texts)

        max_volume = max(item["volume"] for item in filtered_data)
        for item, similarity in zip(filtered_data, similarities):
            item["similarity"] = similarity
            item["score"] = 0.7 * similarity + 0.2 * item["trend"] + 0.1 * (item["volume"] / max_volume)

        sorted_keywords = sorted(filtered_data, key=lambda x: x["score"], reverse=True)
        sorted_keywords = adjust_score_for_repetition(sorted_keywords)

        clusters = cluster_keywords(sorted_keywords, num_clusters=10)
        unique_keywords = select_from_clusters(clusters)

        # Ensure we return exactly 10
        unique_texts = set(kw["text"].strip().lower() for kw in unique_keywords)
        for kw in sorted_keywords:
            text = kw["text"].strip().lower()
            if len(unique_keywords) >= 10:
                break
            if text not in unique_texts:
                unique_keywords.append(kw)
                unique_texts.add(text)

        save_filtered_keywords(conn, unique_keywords)

        # Add selected keywords to the blacklist
        blacklisted_now = [kw["text"].strip().lower() for kw in unique_keywords]
        insert_into_blacklist(conn, blacklisted_now)
        print(f"{len(blacklisted_now)} new keywords added to blacklist.")

        print(f"Saving results to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, "w") as f:
            json.dump(unique_keywords[:10], f, indent=2)

    finally:
        conn.close()

def load_env_from_dotenv():
    # Define the path to the secrets file
    dotenv_path = os.path.abspath("../env_loader/secrets.env")
    print(f"Absolute path to secrets file: {dotenv_path}")

    # Load environment variables from the secrets file
    if load_dotenv(dotenv_path):
        print("Secrets loaded successfully from secrets.env.")
    else:
        print(f"Failed to load secrets.env file from {dotenv_path}")


if __name__ == "__main__":
    load_env_from_dotenv()

    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
    RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
    DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")

    if not all([RAPIDAPI_KEY, RAPIDAPI_HOST, DB_CONNECTION_STRING]):
        raise EnvironmentError(
            "One or more required environment variables are missing!")

    fetch_and_analyze_keywords()
