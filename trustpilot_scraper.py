from playwright.sync_api import sync_playwright
from textblob import TextBlob
import time

URL = "https://www.trustpilot.com/review/squaretrade.com"


def analyze_sentiment(text):
    blob = TextBlob(text)
    print("blob: ", blob)
    return blob.sentiment.polarity


def get_trustpilot_negative_reviews():
    reviews_data = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) "
                "Gecko/20100101 Firefox/117.0"
            )
        )

        page = context.new_page()
        page.goto(URL, timeout=60000)

        # Scroll to load more reviews
        for _ in range(10):
            page.mouse.wheel(0, 5000)
            time.sleep(2)

        review_cards = page.query_selector_all("article[data-service-review-card-paper]")
        if not review_cards:
            print("❌ Trustpilot blocked this session or no reviews found.")
            browser.close()
            return []

        for card in review_cards:
            # Extract rating
            rating_el = card.query_selector("div[data-service-review-rating]")
            try:
                rating = int(rating_el.get_attribute("data-service-review-rating"))
            except:
                rating = None

            # Extract text
            text_el = card.query_selector("p[data-service-review-text-typography]")
            review_text = text_el.inner_text().strip() if text_el else ""

            if not review_text:
                continue

            sentiment = analyze_sentiment(review_text)
            print("sentiment: ", sentiment)

            # Trustpilot doesn’t give direct links for individual reviews
            review_link = URL  

            # Filter for negative only
            if (rating is not None and rating <= 2) or sentiment < 0:
                reviews_data.append({
                    "rating": rating,
                    "review": review_text,
                    "sentiment": sentiment,
                    "link": review_link,
                    "author": "Unknown",
                    "source": "TrustPilot"
                })

        browser.close()

    return reviews_data
