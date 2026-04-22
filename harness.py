import argparse
import asyncio

from aiohttp import ClientSession


async def run(
    api_url: str,
    target_url: str,
    include_links: bool,
    include_media: bool,
) -> None:
    async with ClientSession() as session:
        payload = {
            "url": target_url,
            "include_links": include_links,
            "include_media": include_media,
        }
        async with session.post(f"{api_url}/extract", json=payload) as response:
            payload = await response.json()

    print(f"Status: {response.status}")
    if response.status != 200:
        print(payload)
        return

    print(f"Title: {payload.get('title', '')}")
    print(f"Final URL: {payload.get('url', '')}")
    markdown = payload.get("markdown", "")
    print("Markdown:\n")
    print(markdown)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple runner for the Page Content API")
    parser.add_argument("url", help="URL to fetch and convert to markdown")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8080",
        help="Base URL for the API server",
    )
    parser.add_argument(
        "--include-links",
        dest="include_links",
        action="store_true",
        help="Include link destinations in markdown output (default)",
    )
    parser.add_argument(
        "--no-include-links",
        dest="include_links",
        action="store_false",
        help="Keep link text but remove link destinations from markdown output",
    )
    parser.add_argument(
        "--include-media",
        dest="include_media",
        action="store_true",
        help="Include image markdown output (default)",
    )
    parser.add_argument(
        "--no-include-media",
        dest="include_media",
        action="store_false",
        help="Replace media with placeholders in markdown output",
    )
    parser.set_defaults(include_links=True, include_media=True)

    args = parser.parse_args()
    asyncio.run(
        run(
            args.api_url,
            args.url,
            args.include_links,
            args.include_media,
        ),
    )

