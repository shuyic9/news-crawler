import scrapy
import logging
from json import JSONDecoder
import playwright


class AbcSpider(scrapy.Spider):
    name = "abc"
    start_urls = [
        "https://abcnews.go.com/search?searchtext=israel%20gaza%20hamas%20palestine&type=Story&sort=date"
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
        # Filter out when ABC repeats the same story in different categories
        last_title = None

        while True:
            await page.locator(".ContentRoll").wait_for()
            articles = (
                await page.locator(".ContentRoll__Headline").get_by_role("link").all()
            )

            logging.info(f"Found {len(articles)} links")

            for article in articles:
                link = response.urljoin(await article.get_attribute("href"))
                title = await article.text_content()

                logging.info(f"Operating on article: {link}")

                if not link.startswith("https://abcnews.go.com/"):
                    logging.info("Skipping link that leaves site")
                    continue

                if title == last_title:
                    logging.info("Skipping duplicate article")
                    continue
                last_title = title

                yield scrapy.Request(
                    link,
                    self.parse_article,
                )

                self.article_count += 1

                if self.article_count >= self.max_articles:
                    logging.info(f"Reached max articles limit: {self.max_articles}")
                    await page.close()
                    return

            try:
                await page.locator(
                    "//a[starts-with(@href,'/search') and .='Next']"
                ).click()
            except playwright.async_api.TimeoutError:
                logging.info("No more pages, closing")
                await page.close()
                return

            # Ensure the next page starts loading before trying to pull more links
            await page.locator("//h3[.='Loading...']").wait_for()

    async def errback_close_page(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()

    def parse_article(self, response):
        logging.info(f"Scraping article: {response.url}")

        title = response.xpath("//h1/span/text()").get().strip()
        content = " ".join(
            "".join(p.xpath(".//text()").getall()).strip()
            for p in response.xpath("//div[@data-testid='prism-article-body']/p")
        )

        logging.info(f"Found relevant article: {title}")

        # Locate the script block that sets metadata
        data_identifier = "window['__abcnews__']="
        script_block = response.xpath(
            f'/html/body/script[contains(.,"{data_identifier}")]/text()'
        ).get()

        # Use raw_decode to discard the remaining JS after the metadata
        page_data = JSONDecoder().raw_decode(
            script_block.partition(data_identifier)[2]
        )[0]
        page_metadata = page_data["page"]["content"]["story"]["story"]["metadata"]

        yield {
            "title": title,
            "content": content,
            "url": response.url,
            "publish_date": page_metadata["timestamp"],
            "word_count": len(content.split()),
        }
