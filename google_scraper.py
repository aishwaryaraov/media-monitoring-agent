import requests
from datetime import datetime
from textblob import TextBlob

API_KEY = "AIzaSyDgEqqHfGK--odfAp4gn62P78aSJe028V4"
PLACE_ID = "ChIJp2UYiWKAhYAR6tURKBJKCeY"

GOOGLE_URL = f"https://places.googleapis.com/v1/places/{PLACE_ID}"

def parse_iso8601(dt_str):
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except:
        return None

def is_negative_review(text, rating):
    sentiment = TextBlob(text).sentiment.polarity
    return rating <= 2.5 or sentiment < 0

def get_google_negative_reviews():
    params = {
        "fields": "*",
        "key": API_KEY
    }

    response = requests.get(GOOGLE_URL, params=params, verify=False)
    data = response.json()

    results = []

    if "reviews" not in data:
        return results

    for review in data["reviews"]:
        rating = review.get("rating", 5)
        text = review.get("text", {}).get("text", "")
        print("google review text: ", text)

        if not text:
            continue

        if is_negative_review(text, rating):
            author = review.get("authorAttribution", {}).get("displayName", "Unknown")
            publish_time = parse_iso8601(review.get("publishTime", ""))
            print("sentiment: ",rating)

            # Construct review link if available (Google doesn't give direct URL)
            review_url = f"https://www.google.com/maps/place/?q=place_id:{PLACE_ID}"

            results.append({
                "rating": rating,
                "review": text,
                "author": author,
                "publish_time": publish_time,
                "link": review_url,
                "source": "Google"
            })

    return results
