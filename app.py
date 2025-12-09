# app.py

from flask import Flask, render_template
from google_scraper import get_google_negative_reviews
from trustpilot_scraper import get_trustpilot_negative_reviews
from pissedconsumer_scraper import get_pissedconsumer_negative_reviews
from datetime import datetime, timezone
import os
import pandas as pd
import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

//Use open API later
GENAI_API_URL = "https://genai-gateway-qa2.apps.app-k8cnp-1.caas.app-npd.aws.cloud.squaretrade.com/api/genai-gateway/v1/questions"
GENAI_DEPLOYMENT_ID = "gpt-4o"

def generate_custom_response(review_text):
    """
    Uses GenAI Gateway API to generate a polite, helpful response to a negative review.
    Keeps response under 100 words.
    """
    try:
        payload = {
            "question": f"Act as the elite CX agent for APP (known as SquareTrade in EU/APAC). Analyze sentiment internally—DO NOT state it in your output. Match the customer's brand usage (APP vs SquareTrade) if visible, otherwise default to 'APP' or a neutral 'We'. Critically: briefly reference the specific product or issue mentioned (e.g., the TV claim) to demonstrate active listening. If the sentiment is positive, express warmth; if negative, empathize with the specific frustration using active, accountable language (e.g., 'I'm sorry the replacement options didn't match the quality of your original TV') and avoid passive phrases like 'expectations didn't align' or 'inconvenience caused.' If contact is needed for resolution, direct them to the appropriate URL squaretrade.com/contact for Global/US, squaretrade.eu/contact-us for EU/UK (do NOT provide physical addresses for returns), or squaretrade.com.au/contact for APAC. Output ONLY the final direct response: {review_text}",
            "deployment_id": GENAI_DEPLOYMENT_ID
        }
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }

        response = requests.post(GENAI_API_URL, headers=headers, data=json.dumps(payload), verify=False)
        response.raise_for_status()

        data = response.json()
        # Adjust this based on the actual response JSON structure
        # Assuming the response contains 'answer' field
        return data.get("answer", "Thank you for your feedback. We are looking into this issue.")
    except Exception as e:
        print("Error generating response via GenAI:", e)
        return "Thank you for your feedback. We are looking into this issue."

def sort_reviews_by_date(reviews):
    return sorted(
        reviews,
        key=lambda x: (x.get("publish_time") or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True
    )

def export_reviews_to_excel(reviews):
    """
    Exports all reviews with generated responses into an Excel file.
    """
    try:
        df = pd.DataFrame(reviews)
        df.to_excel("exported_reviews.xlsx", index=False)
        print("Excel export completed: exported_reviews.xlsx")
    except Exception as e:
        print("Excel export error:", e)

@app.route("/")
def dashboard():
    google_reviews = get_google_negative_reviews()
    trustpilot_reviews = get_trustpilot_negative_reviews()
    pissedconsumer_reviews = get_pissedconsumer_negative_reviews()

    all_reviews = []

    for review in google_reviews + trustpilot_reviews + pissedconsumer_reviews:
        review_copy = review.copy()
        review_copy["suggested_response"] = generate_custom_response(review["review"])
        all_reviews.append(review_copy)

    all_reviews = sort_reviews_by_date(all_reviews)

    # Export to Excel on load
    export_reviews_to_excel(all_reviews)

    total_reviews = len(all_reviews)
    subject = f"Review Alert: {total_reviews} Issues Need Attention"
    
    # Example email body: list first 5 reviews
    body = "Latest Customer Pulse: Top 5 Issues:\n\n"
    for review in all_reviews[:5]:
        body += f"""
    <p>
        <strong>Source:</strong> {review.get('source')}<br>
        <strong>Author:</strong> {review.get('author','Anonymous')}<br>
        <strong>Review:</strong> {review.get('review')}<br>
        <strong>Original post:</strong> {review.get('link')}<br>
        <strong>Suggested Response:</strong> {review.get('suggested_response')}<br>
    </p>
    <hr>
    """
        
        #body += f"Source: {review.get('source')}\n"
        #body += f"Author: {review.get('author','Anonymous')}\n"
        #body += f"Review: {review.get('review')}\n"
        #body += f"Original post: {review.get('link')}\n"
        #body += f"Suggested Response: {review.get('suggested_response')}\n"
        #body += "-------------------------------------\n"

    send_email(subject, body, ["ammarathe@squaretrade.com", "aivenkat@squaretrade.com"])  

    return render_template("dashboard.html", reviews=all_reviews)

def send_email(subject, body, to_emails):
    """
    Sends an email with the given subject and body to a list of recipients.
    """
    # --- Email configuration ---
    SMTP_SERVER = "smtp.gmail.com"  # For Gmail; change if using another provider
    SMTP_PORT = 587
    EMAIL_ADDRESS = "marketmonitor2025@gmail.com"  # Replace with your email
    EMAIL_PASSWORD = "odqp pngw opmt jiub"    # For Gmail, use an App Password

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_emails, msg.as_string())
        server.quit()
        print(f"✅ Email sent to {', '.join(to_emails)}")
    except Exception as e:
        print("❌ Error sending email:", e)

if __name__ == "__main__":
    app.run(debug=True)
