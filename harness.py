import argparse
import asyncio
import time

from aiohttp import ClientSession


async def run(
    api_url: str,
    target_url: str,
    include_links: bool,
    include_media: bool,
    concurrency: int,
    count: int,
) -> None:
    async with ClientSession() as session:
        payload = {
            "url": target_url,
            "include_links": include_links,
            "include_media": include_media,
        }

        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def one_request(index: int) -> tuple[int, dict, int, int]:
            started = time.monotonic()
            async with semaphore:
                async with session.post(f"{api_url}/extract", json=payload) as response:
                    body = await response.json()
                    elapsed_ms = int((time.monotonic() - started) * 1000)
                    return index, body, response.status, elapsed_ms

        total_started = time.monotonic()
        results = await asyncio.gather(*(one_request(i + 1) for i in range(count)))
        total_elapsed_ms = int((time.monotonic() - total_started) * 1000)

    ok = 0
    for index, body, status, elapsed_ms in results:
        print(f"Request {index}: status={status} elapsed_ms={elapsed_ms}")
        if status == 200:
            ok += 1
        else:
            print(body)

    print(f"Completed: {ok}/{count} succeeded, total_elapsed_ms={total_elapsed_ms}")

    first_ok = next((body for _, body, status, _ in results if status == 200), None)
    if first_ok:
        print(f"Sample Title: {first_ok.get('title', '')}")
        print(f"Sample Final URL: {first_ok.get('url', '')}")
        if count == 1:
            print(f"Sample Markdown:\n{first_ok.get('markdown', '')}...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple runner for the Page Content API")
    parser.add_argument("url", help="URL to fetch and convert to markdown")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8080",
        help="Base URL for the API server",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Maximum number of in-flight requests",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Total number of requests to send",
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
            args.concurrency,
            args.count,
        ),
    )

