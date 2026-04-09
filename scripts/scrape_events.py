"""Scrape events from the mcrcoderdojo.org.uk WordPress site.

Events are a custom post type with no REST API endpoint, so we scrape them
directly. They are saved as regular posts tagged with "events".
"""
from datetime import datetime
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup
from structlog import get_logger


POSTS_DIR = Path(__file__).parent.parent / "content" / "posts"
EVENTS_INDEX_URL = "https://mcrcoderdojo.org.uk/events/"
SITE_DOMAINS = ("https://mcrcoderdojo.org.uk", "http://mcrcoderdojo.org.uk")

logger = get_logger()


def fetch_event_urls() -> list[str]:
    logger.info("Fetching events index", url=EVENTS_INDEX_URL)
    response = requests.get(EVENTS_INDEX_URL)
    response.raise_for_status()
    bs = BeautifulSoup(response.text, "html.parser")
    urls = sorted({
        a["href"].rstrip("/")
        for a in bs.find_all("a", href=True)
        if "/event/" in a["href"]
    })
    logger.info("Found event URLs", count=len(urls))
    return urls


def parse_event_date(bs: BeautifulSoup, slug: str) -> datetime:
    """Extract event date from the Date & Time content block."""
    for col in bs.find_all("div", class_="col"):
        text = col.get_text(separator="\n", strip=True)
        if "Date" in text:
            for line in text.splitlines():
                line = line.strip()
                for fmt in ("%d %B %Y", "%d %b %Y"):
                    try:
                        return datetime.strptime(line, fmt)
                    except ValueError:
                        pass
    # Fall back to parsing from slug e.g. "20-sunday-8th-february-2015"
    parts = slug.split("-")
    for i, part in enumerate(parts):
        for fmt in ("%B", "%b"):
            try:
                datetime.strptime(part.capitalize(), fmt)
                # Found a month — try combining with surrounding parts
                candidates = [
                    " ".join(parts[max(0, i-1):i+2]),  # day month year
                    " ".join(parts[i:i+2]),              # month year
                ]
                for candidate in candidates:
                    for fmt2 in ("%dth %B %Y", "%dst %B %Y", "%dnd %B %Y", "%drd %B %Y",
                                 "%d %B %Y", "%B %Y"):
                        try:
                            return datetime.strptime(candidate.capitalize(), fmt2)
                        except ValueError:
                            pass
            except ValueError:
                pass
    logger.warning("Could not parse event date, using epoch", slug=slug)
    return datetime(2000, 1, 1)


def scrape_event(url: str) -> dict | None:
    slug = url.rstrip("/").split("/")[-1]
    logger.info("Scraping event", slug=slug)

    response = requests.get(url + "/")
    response.raise_for_status()
    bs = BeautifulSoup(response.text, "html.parser")

    title_tag = bs.find("h1", class_="entry-title")
    if not title_tag:
        logger.warning("No title found, skipping", slug=slug)
        return None
    title = title_tag.get_text(strip=True)

    content_div = bs.find("div", class_="entry-content")

    cover_image_url = None
    thumbnail = bs.find("div", class_="post-thumbnail")
    if thumbnail:
        img = thumbnail.find("img")
        if img and img.get("src", "").startswith("http"):
            cover_image_url = img["src"]

    published = parse_event_date(bs, slug)

    return {
        "slug": slug,
        "title": title,
        "published": published,
        "content_bs": content_div,
        "cover_image_url": cover_image_url,
    }


def rewrite_links(bs: BeautifulSoup):
    for a_tag in bs.find_all("a", href=True):
        href = a_tag["href"]
        for domain in SITE_DOMAINS:
            if href.startswith(domain):
                a_tag["href"] = href[len(domain):] or "/"
                break


def save_event(event: dict):
    slug = event["slug"]
    post_dir = POSTS_DIR / slug
    post_dir.mkdir(exist_ok=True)

    cover_image = None
    if event["cover_image_url"]:
        img_url = event["cover_image_url"]
        img_filename = Path(img_url).name
        img_path = post_dir / "images" / img_filename
        img_path.parent.mkdir(exist_ok=True)
        if not img_path.exists():
            logger.info("Downloading cover image", src=img_url)
            r = requests.get(img_url)
            img_path.write_bytes(r.content)
        cover_image = img_filename

    content_bs = event["content_bs"]
    if content_bs:
        for img in content_bs.find_all("img"):
            src = img.get("src", "")
            if src.startswith("http"):
                img_filename = Path(src).name
                img_path = post_dir / "images" / img_filename
                img_path.parent.mkdir(exist_ok=True)
                if not img_path.exists():
                    logger.info("Downloading image", src=src)
                    r = requests.get(src)
                    img_path.write_bytes(r.content)
                img["src"] = f"images/{img_filename}"
                for attr in ("srcset", "aria-describedby"):
                    if attr in img.attrs:
                        del img[attr]
        rewrite_links(content_bs)
        content_html = content_bs.prettify()
    else:
        content_html = ""

    published = event["published"]
    metadata = {
        "title": event["title"],
        "slug": slug,
        "published": published.isoformat(timespec="seconds"),
        "modified": published.isoformat(timespec="seconds"),
        "tags": ["events"],
    }
    if cover_image:
        metadata["cover_image"] = cover_image

    (post_dir / "meta.yml").write_text(yaml.dump(metadata, allow_unicode=True))
    (post_dir / "index.html").write_text(content_html)
    logger.info("Saved event", slug=slug, published=published.date().isoformat())


if __name__ == "__main__":
    urls = fetch_event_urls()
    for url in urls:
        slug = url.rstrip("/").split("/")[-1]
        post_dir = POSTS_DIR / slug
        if post_dir.exists():
            logger.info("Skipping existing event", slug=slug)
            continue
        event = scrape_event(url)
        if event:
            save_event(event)
