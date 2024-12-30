import requests
import json
from sentence_transformers import SentenceTransformer, util
import time
from concurrent.futures import ThreadPoolExecutor

# API and configuration
RAPIDAPI_KEY = "e42e36094amsh106deea428ceb26p1c5311jsnb0be3386e7c0"
RAPIDAPI_HOST = "google-keyword-insight1.p.rapidapi.com"
OUTPUT_FILE = "keywords.json"

# Configuration
SEED_KEYWORDS = [
    "Samsung 57-inch G95NC gaming monitor review",
    "Nvidia RTX 4090 performance benchmarks",
    "Baldur's Gate 3 gameplay strategies",
    "Louqe Ghost S1 small form factor build guide",
    "Quantum computing impact on gaming",
    "Best gaming laptops for 2024",
    "Cloud gaming platforms comparison",
    "Indie games worth playing in 2024",
    "Top gaming headsets with spatial audio",
    "Graphics cards for 4K gaming",
    "AI in gaming: future trends",
    "Latest gaming mouse reviews",
    "Cyberpunk 2077 mods and updates",
    "Portable monitors for gaming on the go",
    "Steam Deck game compatibility tips",
    "Building a budget gaming PC in 2024",
    "Gaming chairs with ergonomic features",
    "Top-rated mechanical keyboards for gaming",
    "How to optimize GPU performance for gaming",
    "Role-playing games with co-op modes"
]
LOCATION = "GB"
LANGUAGE = "en"
BLACKLIST = ["game", "games", "technology", "news", "trends"]
INTENT_PATTERNS = ["how to", "best", "top",
                   "reviews", "comparison", "latest", "deals"]

# Load the SentenceTransformer model
print("Loading SentenceTransformer model...")
start_time = time.time()
model = SentenceTransformer("all-MiniLM-L6-v2")
print(f"Model loaded in {time.time() - start_time:.2f} seconds.")

# Helper functions


def fetch_keywords(endpoint, params):
    url = f"https://{RAPIDAPI_HOST}/{endpoint}"
    headers = {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def calculate_similarity_batch(seed_keywords, texts):
    seed_embeddings = model.encode(seed_keywords, convert_to_tensor=True)
    text_embeddings = model.encode(texts, convert_to_tensor=True)
    cosine_scores = util.cos_sim(seed_embeddings, text_embeddings)
    max_scores = cosine_scores.max(dim=0).values.cpu().tolist()
    return max_scores


def is_too_generic(keyword, seed_keywords, other_keywords, similarity_threshold=0.8):
    """
    Check if a keyword is overly generic:
    1. High similarity to all seed keywords.
    2. High pairwise similarity to other shortlisted keywords.
    """
    keyword_embedding = model.encode(keyword, convert_to_tensor=True)
    seed_embeddings = model.encode(seed_keywords, convert_to_tensor=True)
    other_embeddings = model.encode(other_keywords, convert_to_tensor=True)

    # Similarity to seed keywords
    seed_similarity = util.cos_sim(
        keyword_embedding, seed_embeddings).mean().item()
    if seed_similarity > similarity_threshold:
        return True

    # Pairwise similarity to other keywords
    if other_keywords:
        pairwise_similarity = util.cos_sim(
            keyword_embedding, other_embeddings).mean().item()
        if pairwise_similarity > similarity_threshold:
            return True

    return False


def fetch_and_analyze_keywords():
    all_keywords = []
    max_volume = 0  # Track max volume for weighting
    total_start_time = time.time()

    def fetch_data_for_seed(seed):
        try:
            keysuggest_data = fetch_keywords(
                "keysuggest", {"keyword": seed, "location": LOCATION, "lang": LANGUAGE})
            globalkey_data = fetch_keywords(
                "globalkey", {"keyword": seed, "lang": LANGUAGE})
            topkeys_data = fetch_keywords(
                "topkeys", {"keyword": seed, "location": LOCATION, "lang": LANGUAGE})
            return keysuggest_data + globalkey_data + topkeys_data
        except Exception as e:
            print(f"Error fetching data for seed '{seed}': {e}")
            return []

    # Fetch data concurrently
    print("Fetching data concurrently for all seed keywords...")
    with ThreadPoolExecutor() as executor:
        combined_data_lists = list(executor.map(
            fetch_data_for_seed, SEED_KEYWORDS))

    # Flatten combined data
    combined_data = [
        item for sublist in combined_data_lists for item in sublist]
    print(f"Fetched {len(combined_data)} total keywords.")

    # Filter before similarity analysis
    filtered_data = [
        item for item in combined_data
        if (
            item.get("volume", 0) > 1000 and
            item.get("competition_level", "").lower() == "low" and
            item.get("trend", 0) > 0 and
            len(item.get("text", "").split()) > 2 and
            item.get("text", "").lower() not in BLACKLIST
        )
    ]
    print(f"{len(filtered_data)} keywords passed initial filters.")

    # Semantic similarity analysis
    texts = [item["text"] for item in filtered_data]
    print("Starting semantic similarity analysis...")
    similarities = calculate_similarity_batch(SEED_KEYWORDS, texts)

    # Add similarity scores
    shortlisted_keywords = []
    for idx, (item, similarity) in enumerate(zip(filtered_data, similarities), 1):
        keyword_text = item.get("text", "")
        item.update({"similarity": similarity})

        # Reject overly generic keywords
        if is_too_generic(keyword_text, SEED_KEYWORDS, shortlisted_keywords):
            print(f"Rejected generic keyword: {keyword_text}")
            continue

        shortlisted_keywords.append(keyword_text)
        all_keywords.append(item)

        # Show progress
        progress = (idx / len(filtered_data)) * 100
        print(
            f"Processed {idx}/{len(filtered_data)} keywords ({progress:.2f}%).")

    # Remove duplicates based on keyword text
    print("Removing duplicates...")
    unique_keywords = {kw["text"]: kw for kw in all_keywords}.values()

    # Sort by similarity and take the top 10
    print("Selecting top 10 keywords by similarity...")
    top_keywords = sorted(
        unique_keywords, key=lambda x: x["similarity"], reverse=True)[:10]

    # Further refine top keywords with scoring
    print("Scoring top keywords...")
    for keyword in top_keywords:
        is_intent_keyword = any(
            pattern in keyword["text"].lower() for pattern in INTENT_PATTERNS)
        volume = keyword.get("volume", 0)
        trend = keyword.get("trend", 0.0)

        if volume > max_volume:
            max_volume = volume

        score = (0.7 * keyword["similarity"]) + (0.2 * trend) + \
                (0.1 * (volume / max_volume)) + (0.1 * is_intent_keyword)
        keyword.update({"score": score})

    # Sort final top 10 by score
    sorted_keywords = sorted(
        top_keywords, key=lambda x: x["score"], reverse=True)

    # Save results to JSON
    print(f"Saving results to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(sorted_keywords, f, indent=2)

    print(
        f"Top 10 keywords saved to '{OUTPUT_FILE}'. Total runtime: {time.time() - total_start_time:.2f} seconds.")


# Run the script
if __name__ == "__main__":
    fetch_and_analyze_keywords()
