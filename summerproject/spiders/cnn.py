import scrapy
import logging
import re
import playwright


class CnnSpider(scrapy.Spider):
    name = "cnn"
    start_urls = [
        'https://www.cnn.com/search?q=israel+gaza+hamas+palestine+"west+bank"=&types=article',
    ]
    custom_settings = {
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
        },
        "DUPEFILTER_DEBUG": True,
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
        cards_locator = page.locator("//div[@data-editable='cards']")

        while True:
            await cards_locator.wait_for()

            article_links = [
                await e.get_attribute("data-open-link")
                for e in await cards_locator.locator(
                    "//div[@data-component-name='card']"
                ).all()
            ]

            logging.info(f"Found {len(article_links)} article links")

            for link in article_links:
                logging.info(f"Operating on article: {link}")
                yield scrapy.Request(
                    response.urljoin(link),
                    self.parse_article,
                )

                self.article_count += 1

                if self.article_count >= self.max_articles:
                    logging.info(f"Reached max articles limit: {self.max_articles}")
                    await page.close()
                    return

            try:
                await page.locator("div.pagination-arrow-right.text-active").click()
            except playwright.async_api.TimeoutError:
                logging.info("No more pages, closing")
                await page.close()
                return

            logging.info("Following next page")
            # HACK: ensure that the next page has loaded in properly
            await page.wait_for_timeout(5000)

    async def errback_close_page(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()

    def parse_article(self, response):
        logging.info(f"Scraping article: {response.url}")

        title = response.css("h1#maincontent::text").get().strip()
        content = " ".join(
            "".join(p.xpath(".//text()").getall()).strip()
            for p in response.xpath("//p[@data-component-name='paragraph']")
        )

        logging.info(f"Found relevant article: {title}")

        # Locate the script block that sets window.CNN metadata
        script_block = response.xpath(
            "/html/head/script[contains(.,'window.CNN = ')]"
        ).get()
        published_date = re.search(" published_date: '(.*)',", script_block).group(1)
        # TODO: A lot of articles seem to have an empty author field, may need to extract from page content
        author = re.search(" author: '(.*)',", script_block).group(1)
        affiliation = re.search(" section: '(.*)',", script_block).group(1)

        yield {
            "title": title,
            "content": content,
            "publish_date": published_date,
            "url": response.url,
            "author": author,
            "word_count": len(content.split()),
            "affiliation": affiliation,
        }
