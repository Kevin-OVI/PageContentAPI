import logging

from aiohttp import web

from page_content_api import create_app

LOGGER = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    LOGGER.info("Starting PageContentAPI server on 0.0.0.0:8080")
    web.run_app(create_app(), host="0.0.0.0", port=8080)
