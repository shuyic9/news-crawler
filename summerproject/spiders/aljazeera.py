import scrapy
import logging
import json


class AljazeeraSpider(scrapy.Spider):
    name = "aljazeera"
    start_urls = ["https://www.aljazeera.com/tag/israel-palestine-conflict/"]
    custom_settings = {
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
        },
        "DUPEFILTER_DEBUG": True,
    }
    pages = 10

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

        for i in range(1, self.pages):
            await page.get_by_test_id("show-more-button").click()
            await page.wait_for_timeout(3000)

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
        title = response.xpath("//header//h1/text()").get().strip()
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

        yield {
            "title": title,
            "content": content,
            "publish_date": react_root["datePublished"],
            "url": response.url,
            "author": react_root["author"]["name"],
            "word_count": len(content.split()),
        }
