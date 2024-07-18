import scrapy
import logging
from scrapy_playwright.page import PageMethod


class CnnSpider(scrapy.Spider):
    name = "cnn"
    start_urls = [
        "https://www.cnn.com/search?q=palestine+israel+gaza&types=article",
    ]
    custom_settings = {
        # "PLAYWRIGHT_LAUNCH_OPTIONS": {
        #     "headless": False,
        # },
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60 * 1000,
    }
    max_articles = 50
    article_count = 0

    def start_requests(self):
        for url in self.start_urls:
            logging.info(f"Starting request for URL: {url}")
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                },
                errback=self.errback_close_page,
            )

    async def parse(self, response):
        page = response.meta["playwright_page"]

        while True:
            await page.wait_for_selector('div[data-component-name="card"]')

            article_links = [
                await e.get_attribute("data-open-link")
                for e in await page.locator('div[data-component-name="card"]').all()
            ]

            logging.info(f"Found {len(article_links)} article links")

            for link in article_links:
                yield scrapy.Request(
                    response.urljoin(link),
                    self.parse_article,
                    meta={
                        "playwright": True,
                        "playwright_page_methods": {
                            "published_date": PageMethod(
                                "evaluate", "window.CNN.contentModel.published_date"
                            ),
                            "last_updated_date": PageMethod(
                                "evaluate", "window.CNN.contentModel.last_updated_date"
                            ),
                        },
                    },
                )

                if self.article_count >= self.max_articles:
                    logging.info(f"Reached max articles limit: {self.max_articles}")
                    await page.close()
                    return

                self.article_count += 1

            next_button = page.locator("div.pagination-arrow-right.text-active")
            # FIXME: That's not how it works at all, next_button will never be None. Come up with a better way for checking this.
            if next_button is None:
                logging.info("No more pages, closing")
                await page.close()
                return

            logging.info("Following next page")
            await next_button.click()

    async def errback_close_page(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()

    def parse_article(self, response):
        logging.info(f"Scraping article: {response.url}")

        title = response.css("h1#maincontent::text").get().strip()
        content = " ".join(
            map(
                str.strip,
                response.css(
                    'p.paragraph[data-component-name="paragraph"]::text'
                ).getall(),
            )
        )
        page_methods = response.meta["playwright_page_methods"]

        logging.info(f"Found relevant article: {title}")

        yield {
            "title": title,
            "url": response.url,
            "content": content,
            "published_date": page_methods["published_date"].result,
            "last_updated_date": page_methods["last_updated_date"].result,
        }
