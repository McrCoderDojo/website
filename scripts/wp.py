from datetime import datetime
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, model_validator
from structlog import get_logger


POSTS_DIR = Path(__file__).parent.parent / "content" / "posts"
POSTS_DIR.mkdir(exist_ok=True)

logger = get_logger()


class WithRendered(BaseModel):
    rendered: str


class Post(BaseModel):
    published: datetime = Field(alias="date")
    modified: datetime
    slug: str
    title: WithRendered
    content: WithRendered
    featured_media: int = 0
    tags_list: list[str] = []
    class_list: list[str] = []
    embedded: dict = Field(alias="_embedded", default_factory=dict)

    @model_validator(mode="after")
    def validate_tags(self):
        for value in self.class_list:
            parts = value.split("-")
            if parts[0] == "tag":
                self.tags_list.append("-".join(parts[1:]))
        return self

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


def fetch_posts_json(url: str) -> list[Post]:
    logger.info("Fetching posts", url=url)
    response = requests.get(url, params={"_embed": "true"})
    response.raise_for_status()
    posts_data = response.json()
    logger.info("Fetched posts", count=len(posts_data))
    return [Post.model_validate(post) for post in posts_data]


def save_posts(url: str):
    posts = fetch_posts_json(url)
    for post in posts:
        save_post(post)


def save_post(post: Post):
    post_dir = POSTS_DIR / post.slug
    post_dir.mkdir(exist_ok=True)
    logger.info("Saving post", slug=post.slug, path=str(post_dir))

    cover_image = None
    image_url = post.get_featured_image_url()
    if image_url:
        img_filename = Path(image_url).name
        img_path = post_dir / "images" / img_filename
        img_path.parent.mkdir(exist_ok=True)
        if not img_path.exists():
            logger.info("Downloading cover image", src=image_url)
            r = requests.get(image_url)
            img_path.write_bytes(r.content)
        cover_image = img_filename

    author = post.get_author_name()

    metadata = {
        "title": post.title.rendered,
        "slug": post.slug,
        "published": post.published.isoformat(timespec="seconds"),
        "modified": post.modified.isoformat(timespec="seconds"),
        "tags": post.tags_list,
    }
    if cover_image:
        metadata["cover_image"] = cover_image
    if author:
        metadata["author"] = author

    metadata_file = post_dir / "meta.yml"
    metadata_file.write_text(yaml.dump(metadata))
    post_file = post_dir / "index.html"
    bs = BeautifulSoup(post.content.rendered, "html.parser")
    for img in bs.find_all("img"):
        source = img["src"]
        if source.startswith("http"):
            r = requests.get(source)
            img_path = post_dir / "images" / Path(source).name
            img_path.parent.mkdir(exist_ok=True)
            if not img_path.exists():
                logger.info("Downloading image", src=source)
                img_path.write_bytes(r.content)
            img["src"] = f"images/{Path(source).name}"
            if "srcset" in img.attrs:
                del img["srcset"]
            if "aria-describedby" in img.attrs:
                del img["aria-describedby"]
        else:
            logger.warn("Skipping non-http image", src=source)

    for a_tag in bs.find_all("a", href=True):
        if a_tag["href"].startswith("https://mcrcoderdojo.org/"):
            img = a_tag.find("img")
            if img:
                a_tag.unwrap()
    post_file.write_text(bs.prettify())


if __name__ == "__main__":
    urls = [
        "https://mcrcoderdojo.org.uk/wp-json/wp/v2/posts?per_page=100",
    ]
    for url in urls:
        save_posts(url)
