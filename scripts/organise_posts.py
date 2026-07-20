"""Move newsletter and event posts into their own subdirectories.

Newsletters: identified via the WordPress API (category 'newsletters', ID 2).
Events: identified by tag 'events' in meta.yml (scraped, no REST endpoint).
"""
import shutil
from pathlib import Path

import requests
import yaml
from structlog import get_logger

POSTS_DIR = Path(__file__).parent.parent / "content" / "posts"
WP_API = "https://mcrcoderdojo.org.uk/wp-json/wp/v2/posts"
NEWSLETTERS_CATEGORY_ID = 2

logger = get_logger()


def fetch_newsletter_slugs() -> set[str]:
    slugs = set()
    page = 1
    while True:
        logger.info("Fetching newsletters page", page=page)
        response = requests.get(WP_API, params={
            "categories": NEWSLETTERS_CATEGORY_ID,
            "per_page": 100,
            "page": page,
            "_fields": "slug",
        })
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        slugs.update(p["slug"] for p in data)
        if len(data) < 100:
            break
        page += 1
    logger.info("Found newsletter slugs", count=len(slugs))
    return slugs


def find_event_slugs() -> set[str]:
    slugs = set()
    for meta_file in POSTS_DIR.glob("*/meta.yml"):
        with open(meta_file) as f:
            meta = yaml.safe_load(f)
        if meta and "events" in (meta.get("tags") or []):
            slugs.add(meta_file.parent.name)
    logger.info("Found event slugs", count=len(slugs))
    return slugs


def move_posts(slugs: set[str], target_dir: Path):
    target_dir.mkdir(exist_ok=True)
    for slug in sorted(slugs):
        src = POSTS_DIR / slug
        dst = target_dir / slug
        if not src.exists():
            logger.warning("Source directory not found, skipping", slug=slug)
            continue
        if dst.exists():
            logger.info("Already in place, skipping", slug=slug)
            continue
        logger.info("Moving", slug=slug, dst=str(dst))
        shutil.move(str(src), str(dst))


def main():
    newsletter_slugs = fetch_newsletter_slugs()
    event_slugs = find_event_slugs()

    overlap = newsletter_slugs & event_slugs
    if overlap:
        logger.warning("Slugs in both newsletters and events", slugs=overlap)

    move_posts(newsletter_slugs, POSTS_DIR / "newsletters")
    move_posts(event_slugs, POSTS_DIR / "events")


if __name__ == "__main__":
    main()
