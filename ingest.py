import os
import json
import time
import signal
import logging
from datetime import datetime

import praw
from azure.eventhub import EventHubProducerClient, EventData
from transformers import pipeline

# ------------- Config & Logging -------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ingest")

REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "RedditEmotionStreamer/1.0")

EVENTHUB_CONNECTION_STRING = os.environ.get("EVENTHUB_CONNECTION_STRING")
EVENTHUB_NAME = os.environ.get("EVENTHUB_NAME")  # optional if EntityPath is inside the conn string

KEYWORDS = [k.strip() for k in os.environ.get("KEYWORDS", "donald trump,trump").split(",") if k.strip()]
SUBREDDITS = os.environ.get("SUBREDDITS", "all")  # e.g. "all" or "news+politics+worldnews"

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "50"))
FLUSH_SECONDS = int(os.environ.get("FLUSH_SECONDS", "5"))
SLEEP_ON_ERROR = int(os.environ.get("SLEEP_ON_ERROR", "5"))
TEXT_MAX_CHARS = int(os.environ.get("TEXT_MAX_CHARS", "512"))

STOP = False


def _handle_stop(signum, frame):
    global STOP
    STOP = True


signal.signal(signal.SIGTERM, _handle_stop)
signal.signal(signal.SIGINT, _handle_stop)


def text_matches_keywords(text: str) -> bool:
    return any(k in text.lower() for k in KEYWORDS)


def main():
    # ---- Reddit ----
    if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
        raise ValueError("Reddit credentials are missing. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.")

    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )

    # ---- Event Hub ----
    if not EVENTHUB_CONNECTION_STRING:
        raise ValueError("EVENTHUB_CONNECTION_STRING is missing.")

    producer = EventHubProducerClient.from_connection_string(
        conn_str=EVENTHUB_CONNECTION_STRING,
        eventhub_name=EVENTHUB_NAME  # can be None if EntityPath already in the conn string
    )

    # ---- Emotion model ----
    logger.info("Loading emotion model: j-hartmann/emotion-english-distilroberta-base")
    emotion_pipeline = pipeline(
        task="text-classification",
        model="j-hartmann/emotion-english-distilroberta-base",
        return_all_scores=True
    )

    def get_emotions(text: str):
        preds = emotion_pipeline(text[:TEXT_MAX_CHARS])[0]
        scores = {p["label"]: round(float(p["score"]), 4) for p in preds}
        top_label = max(scores, key=scores.get)
        top_score = scores[top_label]
        return top_label, top_score, scores

    logger.info(f"Starting Reddit stream on '{SUBREDDITS}' (filtering keywords: {KEYWORDS})")

    batch = []
    last_flush = time.time()

    def flush():
        nonlocal batch, last_flush
        if not batch:
            return
        try:
            producer.send_batch(batch)
            logger.info(f"Sent {len(batch)} events.")
        except Exception:
            logger.exception("Failed to send batch to Event Hub.")
        finally:
            batch = []
            last_flush = time.time()

    try:
        for post in reddit.subreddit(SUBREDDITS).stream.submissions(skip_existing=True):
            if STOP:
                break

            text = f"{post.title or ''} {post.selftext or ''}".strip()
            if not text_matches_keywords(text):
                continue

            try:
                label, score, all_scores = get_emotions(text)
            except Exception:
                logger.exception("Emotion model failed on text, skipping post.")
                continue

            data = {
                "post_id": post.id,
                "text": text,
                "created_utc": datetime.utcfromtimestamp(post.created_utc).isoformat(),
                "subreddit": post.subreddit.display_name,
                "permalink": f"https://www.reddit.com{post.permalink}",
                "emotion": label,
                "score": score,
                "all_emotion_scores": all_scores,
            }

            batch.append(EventData(json.dumps(data)))

            # Flush on size or time
            if len(batch) >= BATCH_SIZE or (time.time() - last_flush) >= FLUSH_SECONDS:
                flush()

    except Exception:
        logger.exception("Fatal error in stream loop.")
    finally:
        # final flush
        flush()
        producer.close()
        logger.info("Shut down cleanly.")


if __name__ == "__main__":
    main()
