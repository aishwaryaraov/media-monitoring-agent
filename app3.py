from flask import Flask, render_template
from google_scraper import get_google_negative_reviews
from trustpilot_scraper import get_trustpilot_negative_reviews
from pissedconsumer_scraper import get_pissedconsumer_negative_reviews
from datetime import datetime, timezone
import pandas as pd
import requests
import ssl
from slack import WebClient
from slack_sdk.errors import SlackApiError

app = Flask(__name__)

ssl_context = ssl._create_unverified_context()
# --- Slack setup ---
SLACK_BOT_TOKEN = "" 
SLACK_CHANNEL = "#market_monitoring_hackathon-2025"  # channel ID or name
slack_client = WebClient(token=SLACK_BOT_TOKEN, ssl=ssl_context)

# --- GenAI setup (example for SquareTrade internal GenAI) ---
GENAI_URL = "https://genai-gateway-qa2.apps.app-k8cnp-1.caas.app-npd.aws.cloud.squaretrade.com/api/genai-gateway/v1/questions"
DEPLOYMENT_ID = "gpt-4o"

def generate_custom_response(review_text):
    payload = {
        "question": f"Keep your responses under 100 words. Generate a custom response for this on behalf of a CX team: {review_text}",
        "deployment_id": DEPLOYMENT_ID
    }
    try:
        response = requests.post(GENAI_URL, json=payload, verify=False, timeout=30)
        response.raise_for_status()
        answer = response.json().get("answer") or response.json().get("answers", [{}])[0].get("answer")
        return answer if answer else "Thank you for your feedback. We are looking into this issue."
    except Exception as e:
        print("Error generating response via GenAI:", e)
        return "Thank you for your feedback. We are looking into this issue."

def sort_reviews_by_date(reviews):
    return sorted(
        reviews,
        key=lambda x: (x.get("publish_time") or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True
    )

def export_reviews_to_excel(reviews, filename="exported_reviews.xlsx"):
    df = pd.DataFrame(reviews)
    df.to_excel(filename, index=False)
    print(f"Excel export completed: {filename}")

def send_review_to_slack(review):
    message = (
        f"*Source:* {review['source']}\n"
        f"*Author:* {review.get('author','Anonymous')}\n"
        f"*Rating / Sentiment:* {review.get('rating', review.get('sentiment'))}\n"
        f"*Review:* {review['review']}\n"
        f"*Suggested Response:* {review.get('suggested_response','')}\n"
        f"*Link:* {review.get('link')}\n"
    )
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
        print(f"✅ Sent review from {review['source']} to Slack")
    except SlackApiError as e:
        print(f"❌ Slack error: {e.response['error']}")

@app.route("/")
def dashboard():
    # --- Get reviews from all sources ---
    google_reviews = get_google_negative_reviews()
    trustpilot_reviews = get_trustpilot_negative_reviews()
    pissedconsumer_reviews = get_pissedconsumer_negative_reviews()

    all_reviews = []

    for review in google_reviews + trustpilot_reviews + pissedconsumer_reviews:
        review_copy = review.copy()
        review_copy["suggested_response"] = generate_custom_response(review["review"])
        all_reviews.append(review_copy)

    all_reviews = sort_reviews_by_date(all_reviews)

    # --- Export to Excel ---
    export_reviews_to_excel(all_reviews)

    # --- Send each negative review to Slack ---
    for review in all_reviews:
        send_review_to_slack(review)

    return render_template("dashboard.html", reviews=all_reviews)

if __name__ == "__main__":
    app.run(debug=True)
