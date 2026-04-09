from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup
from markdownify import markdownify
from pydantic import BaseModel, Field
from structlog import get_logger


PAGES_DIR = Path(__file__).parent.parent / "content" / "pages"
WP_API = "https://mcrcoderdojo.org.uk/wp-json/wp/v2/pages"
SITE_DOMAINS = ("https://mcrcoderdojo.org.uk", "http://mcrcoderdojo.org.uk")

logger = get_logger()

PROBLEMATIC_TAGS = ("iframe", "table", "script", "form")
SLUG_OVERRIDES = {
    "manchester-coderdojo": "home",
}
SKIP_SLUGS = {"blog", "confirmation", "thanks", "newsletters"}


class WithRendered(BaseModel):
    rendered: str


class Page(BaseModel):
    slug: str
    modified: str
    title: WithRendered
    content: WithRendered
    featured_media: int = 0
    embedded: dict = Field(alias="_embedded", default_factory=dict)

    def get_featured_image_url(self) -> str | None:
        if self.featured_media == 0:
            return None
        try:
            media = self.embedded.get("wp:featuredmedia", [])
            if media:
                return media[0].get("source_url")
        except (IndexError, KeyError, TypeError):
            pass
        return None

    def get_author_name(self) -> str | None:
        try:
            authors = self.embedded.get("author", [])
            if authors:
                return authors[0].get("name")
        except (IndexError, KeyError, TypeError):
            pass
        return None


def fetch_all_pages() -> list[Page]:
    pages = []
    page_num = 1
    while True:
        logger.info("Fetching pages", page=page_num)
        response = requests.get(WP_API, params={"per_page": 100, "page": page_num, "_embed": "true"})
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        pages.extend(Page.model_validate(p) for p in data)
        if len(data) < 100:
            break
        page_num += 1
    logger.info("Fetched pages", count=len(pages))
    return pages


def rewrite_links(bs: BeautifulSoup):
    for a_tag in bs.find_all("a", href=True):
        href = a_tag["href"]
        for domain in SITE_DOMAINS:
            if href.startswith(domain):
                a_tag["href"] = href[len(domain):] or "/"
                break


def rewrite_images(bs: BeautifulSoup, page_dir: Path):
    for img in bs.find_all("img"):
        source = img.get("src", "")
        if source.startswith("http"):
            img_path = page_dir / "images" / Path(source).name
            img_path.parent.mkdir(exist_ok=True)
            if not img_path.exists():
                logger.info("Downloading image", src=source)
                r = requests.get(source)
                img_path.write_bytes(r.content)
            img["src"] = f"images/{Path(source).name}"
            for attr in ("srcset", "aria-describedby"):
                if attr in img.attrs:
                    del img[attr]
        else:
            logger.warning("Skipping non-http image", src=source)


def find_problematic_tags(bs: BeautifulSoup) -> list[str]:
    return [tag for tag in PROBLEMATIC_TAGS if bs.find(tag)]


def to_markdown(bs: BeautifulSoup) -> str:
    return markdownify(str(bs), heading_style="ATX", bullets="-").strip()


def save_page(page: Page):
    slug = SLUG_OVERRIDES.get(page.slug, page.slug)
    page_dir = PAGES_DIR / slug
    page_dir.mkdir(exist_ok=True)

    bs = BeautifulSoup(page.content.rendered, "html.parser")

    problematic = find_problematic_tags(bs)
    if problematic:
        logger.warning("Saving as HTML due to problematic tags", slug=page.slug, tags=problematic)
        content_file = page_dir / "index.html"
    else:
        content_file = page_dir / "index.md"

    logger.info("Saving page", slug=page.slug, format=content_file.suffix)

    cover_image = None
    image_url = page.get_featured_image_url()
    if image_url:
        img_filename = Path(image_url).name
        img_path = page_dir / "images" / img_filename
        img_path.parent.mkdir(exist_ok=True)
        if not img_path.exists():
            logger.info("Downloading cover image", src=image_url)
            r = requests.get(image_url)
            img_path.write_bytes(r.content)
        cover_image = img_filename

    author = page.get_author_name()

    metadata = {
        "title": page.title.rendered,
        "slug": slug,
        "modified": page.modified,
    }
    if cover_image:
        metadata["cover_image"] = cover_image
    if author:
        metadata["author"] = author

    (page_dir / "meta.yml").write_text(yaml.dump(metadata, allow_unicode=True))

    rewrite_links(bs)
    rewrite_images(bs, page_dir)

    if content_file.suffix == ".md":
        content_file.write_text(to_markdown(bs))
    else:
        content_file.write_text(bs.prettify())


if __name__ == "__main__":
    pages = fetch_all_pages()
    for page in pages:
        if page.slug in SKIP_SLUGS:
            logger.info("Skipping page", slug=page.slug)
            continue
        save_page(page)
