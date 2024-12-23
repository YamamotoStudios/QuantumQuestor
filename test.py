import requests

url = "https://trends.google.com/trends/api/explore"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
params = {
    "hl": "en-GB",
    "tz": "0",
    "req": '{"comparisonItem":[{"keyword":"gaming","geo":"GB","time":"now 7-d"}],"category":0,"property":""}',
    "token": "<TOKEN_FROM_BROWSER>",
}

response = requests.get(url, headers=headers, params=params)
print(response.text)  # Inspect raw response
