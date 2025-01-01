import requests
import json
from sentence_transformers import SentenceTransformer, util
from sklearn.cluster import AgglomerativeClustering
import time
from concurrent.futures import ThreadPoolExecutor
import os
from collections import Counter

# API and configuration
RAPIDAPI_KEY = ""
RAPIDAPI_HOST = ""
OUTPUT_FILE = "keywords.json"
RAW_CACHE_FILE = "raw_keywords.json"

# Configuration
SEED_KEYWORDS = [
    "top gaming monitors",
    "Nvidia RTX graphics cards",
    "RPG gaming tips",
    "PC building for gamers",
    "quantum technology in games",
    "cloud gaming services",
    "indie video games",
    "headsets for gaming",
    "4K gaming graphics cards",
    "AI in video games",
    "popular gaming mice",
    "Cyberpunk 2077 news",
    "portable gaming screens",
    "Steam Deck gaming tips",
    "affordable gaming PCs",
    "gaming chairs for comfort",
    "mechanical keyboards for gaming",
    "GPU tips for performance",
    "multiplayer role-playing games",
]
LOCATION = "GB"
LANGUAGE = "en"
BLACKLIST = ["game", "games", "technology", "news", "trends"]
INTENT_PATTERNS = ["how to", "review", "guide", "analysis"]

# Load the SentenceTransformer model
print("Loading SentenceTransformer model...")
start_time = time.time()
model = SentenceTransformer("all-MiniLM-L6-v2")
print(f"Model loaded in {time.time() - start_time:.2f} seconds.")


def fetch_keywords(endpoint, params):
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
    """
    Penalize scores for repeated or thematically similar keywords.
    """
    keyword_texts = [kw["text"].lower() for kw in keywords]
    repetition_counts = Counter(keyword_texts)

    for keyword in keywords:
        repetitions = repetition_counts[keyword["text"].lower()]
        if repetitions > 1:
            # Increase penalty with repetitions
            penalty = 0.1 * (repetitions - 1)
            keyword["score"] -= penalty
            # Ensure score doesn't drop below 0
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
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(keywords[idx])

    return clusters


def select_from_clusters(clusters):
    """
    Select the highest-scoring keyword from each cluster to ensure diversity.
    """
    final_keywords = []
    for cluster_id, cluster_keywords in clusters.items():
        best_keyword = max(cluster_keywords, key=lambda x: x["score"])
        final_keywords.append(best_keyword)
    return final_keywords


def fetch_and_analyze_keywords():
    # Check for cached data
    if os.path.exists(RAW_CACHE_FILE):
        with open(RAW_CACHE_FILE, "r") as f:
            print(f"Loading cached keyword data from {RAW_CACHE_FILE}.")
            combined_data = json.load(f)
    else:
        combined_data = []
        print("Fetching data concurrently for all seed keywords...")

        def fetch_data_for_seed(seed):
            try:
                keysuggest_data = fetch_keywords(
                    "keysuggest", {"keyword": seed, "location": LOCATION, "lang": LANGUAGE})
                globalkey_data = fetch_keywords(
                    "globalkey", {"keyword": seed, "lang": LANGUAGE})
                topkeys_data = fetch_keywords(
                    "topkeys", {"keyword": seed, "location": LOCATION, "lang": LANGUAGE})

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
                fetch_data_for_seed, SEED_KEYWORDS))
            combined_data = [
                item for sublist in combined_data_lists for item in sublist
            ]
        print(f"Fetched {len(combined_data)} total keywords.")
        with open(RAW_CACHE_FILE, "w") as f:
            json.dump(combined_data, f, indent=2)

    # Filter before similarity analysis
    filtered_data = [
        item for item in combined_data
        if (
            item.get("volume", 0) > 100 and
            item.get("competition_level", "").lower() in ["low", "medium"] and
            item.get("trend", 0) >= 0 and
            len(item.get("text", "").split()) >= 2 and
            item.get("text", "").strip().lower() not in set(term.lower()
                                                            for term in BLACKLIST)
        )
    ]
    print(f"{len(filtered_data)} keywords passed initial filters.")

    if not filtered_data:
        print("No keywords passed the filters. Adjust thresholds or input data.")
        return

    texts = [item["text"] for item in filtered_data]
    print("Starting semantic similarity analysis...")
    similarities = calculate_similarity_batch(SEED_KEYWORDS, texts)

    max_volume = max(item["volume"] for item in filtered_data)
    for idx, (item, similarity) in enumerate(zip(filtered_data, similarities), 1):
        volume = item["volume"]
        trend = item["trend"]
        item["similarity"] = similarity
        item["score"] = 0.7 * similarity + 0.2 * \
            trend + 0.1 * (volume / max_volume)

    sorted_keywords = sorted(
        filtered_data, key=lambda x: x["score"], reverse=True
    )[:50]

    # Penalize repetition
    sorted_keywords = adjust_score_for_repetition(sorted_keywords)

    # Cluster and select top keywords
    clusters = cluster_keywords(sorted_keywords, num_clusters=10)
    unique_keywords = select_from_clusters(clusters)

    print(f"Saving results to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(unique_keywords[:10], f, indent=2)
    print(f"Top 10 diverse keywords saved to '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    fetch_and_analyze_keywords()
