from dotenv import load_dotenv
import requests
from collections import Counter
from collections import defaultdict
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
        
        # Log response body on error
        if response.status_code == 429:
            print(f"⚠️ Rate limited (429) on {endpoint} for params {params}")
            print(f"🔁 Headers: {response.headers}")
            raise requests.exceptions.RequestException("Rate limit hit (429)")

        response.raise_for_status()

        data = response.json()
        return data if isinstance(data, list) else [data]

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching {endpoint} with params {params}: {e}")
        try:
            print(f"📦 Response content: {response.text}")
        except NameError:
            print("📦 No response object available.")
        raise  # <-- This is the key change



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
        values = [
            (kw["text"], kw["similarity"], kw["score"], datetime.utcnow())
            for kw in filtered_keywords
        ]
        cur.executemany("""
            INSERT INTO filtered_keywords (text, similarity, score, created_at)
            VALUES (%s, %s, %s, %s)
        """, values)
        conn.commit()

def fetch_blacklist(conn, expiry_days=90):
    expiry_cutoff = datetime.utcnow() - timedelta(days=expiry_days)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT term FROM blacklist
            WHERE created_at >= %s
        """, (expiry_cutoff,))
        return set(row[0].strip().lower() for row in cur.fetchall())

def insert_into_blacklist(conn, keywords):
    with conn.cursor() as cur:
        for kw in keywords:
            cur.execute("""
                INSERT INTO blacklist (term, created_at)
                VALUES (%s, %s)
                ON CONFLICT (term) DO NOTHING
            """, (kw.lower(), datetime.utcnow()))
        conn.commit()

def group_keywords_by_category(keywords):
    category_buckets = defaultdict(list)
    for kw in keywords:
        category = kw.get("category", "uncategorized")
        category_buckets[category].append(kw)
    return category_buckets

def select_keywords_by_category_distribution(
    category_buckets,
    categories,
    per_category_limit=2,
    total_limit=10
):
    final_keywords = []
    seen_texts = set()

    for cat in categories:
        top_items = sorted(category_buckets.get(cat, []), key=lambda x: x["score"], reverse=True)[:per_category_limit]
        for kw in top_items:
            norm_text = kw["text"].strip().lower()
            if norm_text not in seen_texts and len(final_keywords) < total_limit:
                final_keywords.append(kw)
                seen_texts.add(norm_text)

    # Fallback to fill up remaining slots
    all_keywords = [kw for bucket in category_buckets.values() for kw in bucket]
    for kw in sorted(all_keywords, key=lambda x: x["score"], reverse=True):
        norm_text = kw["text"].strip().lower()
        if norm_text not in seen_texts and len(final_keywords) < total_limit:
            final_keywords.append(kw)
            seen_texts.add(norm_text)

    return final_keywords

def fetch_data_for_seed_with_backoff(seed, category, max_retries=6, base_delay=6):
    for attempt in range(max_retries):
        try:
            print(f"\nFetching for seed: '{seed}' (attempt {attempt + 1})")

            # Throttle at safe 6s spacing between requests
            results = []
            for endpoint, params in [
                ("keysuggest", {"keyword": seed, "location": "GB", "lang": "en"}),
                ("globalkey", {"keyword": seed, "lang": "en"}),
                ("topkeys", {"keyword": seed, "location": "GB", "lang": "en"}),
            ]:
                result = fetch_keywords_from_api(endpoint, params)
                results.extend(result)
                time.sleep(base_delay)  # Safe delay between each individual request

            # Tag metadata
            for item in results:
                item["seed_keyword"] = seed
                item["category"] = category

            print(f"✅ Got {len(results)} results for '{seed}'")
            return results

        except Exception as e:
            print(f"⚠️ Error on attempt {attempt + 1} for '{seed}': {e}")
            # Increase wait only if there's an error (exponential backoff)
            backoff_delay = base_delay * (attempt + 1) + random.uniform(0.5, 1.5)
            print(f"🔁 Waiting {backoff_delay:.2f}s before retrying...")
            time.sleep(backoff_delay)

    print(f"❌ Failed all {max_retries} attempts for '{seed}'")
    return []


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
                cur.execute("SELECT keyword, category FROM seed_keywords")
                seed_rows = cur.fetchall()
            
            seed_keyword_category_map = {row[0].strip().lower(): row[1] for row in seed_rows}
            seed_keywords = list(seed_keyword_category_map.keys())

            conn.close()
            
            combined_data_lists = []
            
            for seed in seed_keywords:
                category = seed_keyword_category_map.get(seed.lower(), "uncategorized")
                results = fetch_data_for_seed_with_backoff(seed, category)
                combined_data_lists.append(results)

                combined_data = [
                    item for sublist in combined_data_lists for item in sublist]

        # Filter out blacklisted terms
        pre_filter_count = len(combined_data)
        
        filtered_data = []
        skipped_blacklisted = []
        
        filtered_by_category = defaultdict(list)
        CATEGORY_MINIMUM = 15  # How many from each category you *try* to keep
        
        for item in combined_data:
            text = item.get("text", "").strip().lower()
            category = item.get("category", "uncategorized")
        
            if text in blacklist:
                continue
        
            # Loosen filtering for underrepresented categories
            volume_threshold = 50 if category in ["ai_ethics", "engineering", "crossover"] else 100
            competition_ok = item.get("competition_level", "").lower() in ["low", "medium"]
            trend_ok = item.get("trend", 0) >= 0
            phrase_ok = len(text.split()) >= 2
        
            if (
                item.get("volume", 0) > volume_threshold and
                competition_ok and
                trend_ok and
                phrase_ok
            ):
                filtered_by_category[category].append(item)
        
        # Flatten into final list
        filtered_data = []
        for cat_items in filtered_by_category.values():
            filtered_data.extend(cat_items[:CATEGORY_MINIMUM])

        print(f"{len(filtered_data)} keywords passed initial filters.")

        if skipped_blacklisted:
            print(f"{pre_filter_count - len(filtered_data)} keywords ignored due to blacklist or filter failure.")
            print(f"Skipped {len(skipped_blacklisted)} blacklisted keywords:")
            for kw in skipped_blacklisted:
                print(f' - "{kw}"')
            else:
                print("No keywords were skipped due to blacklist.")

        if not filtered_data:
            print("No keywords passed the filters.")
            return

        from collections import Counter
        print("Keyword category distribution (pre-score):")
        print(Counter([k['category'] for k in filtered_data]))

        print("\nSeeds and their categories:")
        for seed, cat in seed_keyword_category_map.items():
            print(f"{cat.ljust(12)} | {seed}")

        texts = [item["text"] for item in filtered_data]
        print("Starting semantic similarity analysis...")
        similarities = calculate_similarity_batch(seed_keywords, texts)

        max_volume = max(item["volume"] for item in filtered_data)
        for item, similarity in zip(filtered_data, similarities):
            item["similarity"] = similarity
            item["score"] = 0.5 * similarity + 0.4 * item["trend"] + 0.1 * (item["volume"] / max_volume)

        sorted_keywords = sorted(filtered_data, key=lambda x: x["score"], reverse=True)
        sorted_keywords = adjust_score_for_repetition(sorted_keywords)

        # Step 1: Group keywords by category
        category_buckets = group_keywords_by_category(sorted_keywords)
        
        # Step 2: Select top 10, balanced by your seed-defined categories
        CATEGORIES = ["lifestyle", "ai_ethics", "engineering", "gaming", "crossover"]
        final_keywords = select_keywords_by_category_distribution(category_buckets, CATEGORIES)

        conn = psycopg2.connect(DB_CONNECTION_STRING)
        save_filtered_keywords(conn, final_keywords)

        # Add selected keywords to the blacklist
        blacklisted_now = [kw["text"].strip().lower() for kw in final_keywords]
        for kw in blacklisted_now:
            print(f"Blacklisting keyword: '{kw}'")
        insert_into_blacklist(conn, blacklisted_now)
        print(f"{len(blacklisted_now)} new keywords added to blacklist.")

        print(f"Saving results to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, "w") as f:
            json.dump(final_keywords[:10], f, indent=2)

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
