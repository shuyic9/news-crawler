import scrapy
import logging
import itertools
import json
import playwright


class AljazeeraSpider(scrapy.Spider):
    name = "aljazeera"
    start_urls = ["https://www.aljazeera.com/tag/israel-palestine-conflict/"]
    custom_settings = {
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
        },
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 10 * 60 * 1000,  # 10 minutes
        "DUPEFILTER_DEBUG": True,
    }
    pages = None

    def start_requests(self):
        for url in self.start_urls:
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
        await page.wait_for_timeout(5000)

        for i in range(1, self.pages) if self.pages is not None else itertools.count():
            try:
                await page.get_by_test_id("show-more-button").click()
                await page.wait_for_timeout(3000)
                if await page.get_by_text("6 Oct 2023").count() > 0:
                    logging.info("Found final article")
                    break
            except playwright.async_api.TimeoutError:
                logging.info("Reached final page")
                break

        article_links = [
            await e.get_attribute("href")
            for e in await page.locator(
                "//a[starts-with(@href,'/news/') or starts-with(@href,'/features/')]"
            ).all()
        ]

        logging.info(f"Found {len(article_links)} article links")

        for link in article_links:
            if link in ("/news/", "/features/"):
                continue

            logging.info(f"Operating on article: {link}")
            yield scrapy.Request(
                response.urljoin(link),
                self.parse_article,
            )

        await page.close()

    async def errback_close_page(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()

    def parse_article(self, response):
        logging.info(f"Scraping article: {response.url}")
        title = response.xpath("//main//h1/text()").get().strip()
        content = " ".join(
            "".join(e for e in p.xpath(".//text()").getall() if not e.isspace()).strip()
            for p in response.xpath("//main[@id='main-content-area']//p")
        )

        logging.info(f"Found relevant article: {title}")

        react_root = next(
            r
            for r in (
                json.loads(x)
                for x in response.xpath(
                    "/html/head//script[@type='application/ld+json' and @data-reactroot='']/text()"
                ).getall()
            )
            if r["@type"] == "NewsArticle"
        )

        author_data = react_root["author"]
        if not isinstance(author_data, list):
            author_data = [author_data]
        authors = ",".join(x["name"] for x in author_data)

        yield {
            "title": title,
            "content": content,
            "publish_date": react_root["datePublished"],
            "url": response.url,
            "author": authors,
            "word_count": len(content.split()),
        }
