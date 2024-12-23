from trendspy import Trends
import json


def fetch_related_trends(keyword, geo="GB"):
    """
    Fetch related trends for a given keyword using TrendSpy.

    Parameters:
        keyword (str): The keyword to search for.
        geo (str): Geographic location (e.g., 'GB' for United Kingdom).

    Returns:
        dict: Trends data, or None if no data is available.
    """
    try:
        # Initialize TrendSpy
        ts = Trends(hl="en-GB")

        # Fetch trending data
        print(f"Fetching trends for keyword: {keyword} in region: {geo}")
        trends_data = ts.related_queries(keyword=keyword, geo=geo)

        # Print raw response for debugging
        print("Raw trends data:", trends_data)

        return trends_data
    except Exception as e:
        print(f"Error fetching trends: {e}")
        return None


if __name__ == "__main__":
    keyword = "gaming"
    geo = "GB"

    # Fetch trends using TrendSpy
    trends = fetch_related_trends(keyword, geo=geo)

    if trends:
        # Save the trends to a JSON file
        with open("trendspy_data.json", "w") as f:
            json.dump(trends, f, indent=2)
        print("Saved trends data to 'trendspy_data.json'")
    else:
        print("No trends data found.")
