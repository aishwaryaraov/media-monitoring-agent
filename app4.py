from flask import Flask, render_template, request
from google_scraper import get_google_negative_reviews
from trustpilot_scraper import get_trustpilot_negative_reviews
from pissedconsumer_scraper import get_pissedconsumer_negative_reviews
from datetime import datetime, timezone
import pandas as pd
import requests
import ssl
import json
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler


app_flask = Flask(__name__)


ssl_context = ssl._create_unverified_context()

# --- Legacy WebClient for posting (optional, can use Bolt's client too) ---
SLACK_BOT_TOKEN = "xoxb-5124627664-10041450707367-1gqyVWPBnX9YmMAgAC4VP3Gh"
SLACK_CHANNEL = "#market_monitoring_hackathon-2025"
slack_client = WebClient(token=SLACK_BOT_TOKEN, ssl=ssl_context)

# --- Slack Bolt setup for interactive components ---
slack_app = App(
    token=SLACK_BOT_TOKEN,  # Use xoxb- token for Bolt
    signing_secret="1844298ac0ca0dcbf094d1755642a134",  # Get from Slack app settings
    client=slack_client
)

slack_handler = SlackRequestHandler(slack_app)

# --- GenAI setup ---
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
    """Send review with interactive acknowledge button using Block Kit"""
    
    # Create unique action_id for this review
    review_id = f"{review['source']}-{datetime.now().timestamp()}"
    
    # Block Kit message with button
    blocks = [
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Source:*\n{review['source']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Author:*\n{review.get('author', 'Anonymous')}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Rating / Sentiment:*\n{review.get('rating', review.get('sentiment'))}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Link:*\n{review.get('link', 'N/A')}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Review:*\n{review['review']}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Suggested Response:*\n{review.get('suggested_response', '')}"
            }
        },
        {
            "type": "actions",
            "block_id": f"actions-{review_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✓ Acknowledge"
                    },
                    "value": review_id,
                    "action_id": "acknowledge_review",
                    "style": "primary"
                }
            ]
        }
    ]
    
    try:
        slack_client.chat_postMessage(
            channel=SLACK_CHANNEL,
            blocks=blocks
        )
        print(f"✅ Sent review from {review['source']} to Slack with acknowledge button")
    except SlackApiError as e:
        print(f"❌ Slack error: {e.response['error']}")


# --- Handle button clicks ---
@slack_app.action("acknowledge_review")
def handle_acknowledge_button(ack, body, respond):
    """Handle acknowledge button click"""
    ack()  # Acknowledge immediately
    
    review_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    user_name = body["user"]["username"]
    
    # Optional: Log acknowledgment to database or file
    print(f"✅ Review acknowledged by <@{user_id}> ({user_name}): {review_id}")
    
    # Send confirmation message
    respond({
        "text": f"Review acknowledged by <@{user_id}> ✓"
    })


@app_flask.route("/slack/events", methods=["POST"])
def slack_events():
    """Slack events endpoint for interactive components"""
    return slack_handler.handle(request)


@app_flask.route("/")
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

    # --- Send each negative review to Slack with acknowledge button ---
    for review in all_reviews:
        send_review_to_slack(review)

    return render_template("dashboard.html", reviews=all_reviews)


if __name__ == "__main__":
    app_flask.run(debug=True)


