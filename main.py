import os
import json
import random
import logging
import time
from dotenv import load_dotenv
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# Load environment variables
def setup_env():
    load_dotenv()
    page_id = os.getenv("FB_PAGE_ID")
    access_token = os.getenv("FB_ACCESS_TOKEN")
    if not page_id or not access_token:
        raise EnvironmentError("FB_PAGE_ID and FB_ACCESS_TOKEN must be set in .env file")
    return page_id, access_token

# Configure logging
def setup_logging(log_file: str = "fb_poster.log"):
    logger = logging.getLogger("fb_poster")
    logger.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.ERROR)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    ch.setFormatter(fmt)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger

# Load JSON database
def load_database(path: str = "data.json") -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Select random book and chapter, limit text to 2000 chars and end on complete sentence
def get_random_chapter(database: list) -> dict:
    book = random.choice(database)
    title = book.get("main_title")
    author = book.get("author")
    chapters = book.get("chapters", {})
    chapter_key = random.choice(list(chapters.keys()))
    chapter = chapters[chapter_key]
    full_text = chapter.get("text", "")

    # Limit to 2000 characters
    excerpt = full_text[:2000]
    # Ensure it ends on a complete sentence (find last period)
    last_period = excerpt.rfind('.')
    if last_period != -1 and last_period > len(excerpt) - 200:
        excerpt = excerpt[:last_period+1]
    else:
        # fallback: use full excerpt
        excerpt = excerpt.rstrip()

    return {
        "title": title,
        "author": author,
        "chapter_name": chapter_key,
        "text": excerpt + ("..." if len(full_text) > len(excerpt) else ""),
        "link": chapter.get("link"),
    }


# Post to Facebook with retry
def post_to_facebook(page_id: str, access_token: str, message: str, link: str = None,
                     max_retries: int = 3, backoff: int = 5, logger=None) -> dict:
    
    url = f"https://graph.facebook.com/v22.0/{page_id}/feed"
    
    payload = {"message": message, "published": "true", "access_token": access_token}
    if link:
        payload["link"] = link

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Post successful: {result.get('id')}")
            return result
        
        except requests.RequestException as e:
            logger.error(f"Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(backoff * attempt)
            else:
                logger.error("Max retries reached. Could not post to Facebook.")
                raise

# FastAPI setup
app = FastAPI()
page_id, access_token = setup_env()
logger = setup_logging()
database = load_database()

class PostResponse(BaseModel):
    post_id: str

@app.post("/post", response_model=PostResponse)
def create_post():
    """Fetch a random chapter and publish to Facebook."""
    try:
        item = get_random_chapter(database)
        message = (
            f"{item['title']}, {item['author']}\n"
            f"{item['chapter_name']}\n\n"
            f"{item['text']}"
        )
        result = post_to_facebook(page_id, access_token, message, item.get("link"), logger=logger)
        return {"post_id": result.get("id")}  # type: ignore
    except Exception as e:
        logger.error(f"Failed to publish post: {e}")
        raise HTTPException(status_code=500, detail=str(e))

