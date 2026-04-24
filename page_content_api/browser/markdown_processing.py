import re

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as html_to_markdown


def _replace_media(content: Tag, tag_name: str, placeholder_prefix: str) -> None:
    for media in content.find_all(tag_name):
        alt_text = media.attrs.get("alt", "")
        if isinstance(alt_text, list):
            alt_text = " ".join(alt_text)
        if alt_text:
            media.replace_with(f"[{placeholder_prefix}: {alt_text}]")
        else:
            media.replace_with(f"[{placeholder_prefix}]")


def html_fragment_to_markdown(
        html: str,
        max_chars: int,
        include_links: bool,
        include_media: bool,
) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})
    content = main or soup.body or soup

    if not include_links:
        for anchor in content.find_all("a"):
            anchor.replace_with(" ".join(anchor.stripped_strings))

    if not include_media:
        _replace_media(content, "img", "Image")
        _replace_media(content, "video", "Video")
        _replace_media(content, "audio", "Audio")

    markdown = html_to_markdown(str(content), heading_style="ATX")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()

    if len(markdown) > max_chars:
        markdown = markdown[:max_chars].rstrip() + "\n\n...\n"

    return markdown
