import scrapy
from scrapy_splash import SplashRequest
import logging

class BbcSpider(scrapy.Spider):
    name = "bbc"
    start_urls = ["https://www.bbc.com/news/topics/c2vdnvdg6xxt"]
    max_articles = 50
    article_count = 0

    custom_settings = {
        'LOG_LEVEL': 'DEBUG',
        'SPLASH_URL': 'http://localhost:8050',
        'DUPEFILTER_CLASS': 'scrapy_splash.SplashAwareDupeFilter',
        'HTTPCACHE_STORAGE': 'scrapy_splash.SplashAwareFSCacheStorage',
        'SPLASH_TIMEOUT': 90,
        'SPLASH_WAIT': 2,
    }

    def start_requests(self):
        for url in self.start_urls:
            logging.info(f"Starting request for URL: {url}")
            yield SplashRequest(
                url,
                self.parse,
                args={'wait': 2},
            )

    def parse(self, response):
        logging.info(f"Processing URL: {response.url}")
        logging.debug(f"Response status: {response.status}")
        logging.debug(f"Response headers: {response.headers}")

        # Adjust the CSS selector based on BBC News HTML structure
        article_links = response.css('a[href*="/news/articles/"][data-testid="internal-link"]::attr(href)').getall()
        logging.info(f"Found {len(article_links)} article links")

        for link in article_links:
            if self.article_count >= self.max_articles:
                logging.info(f"Reached max articles limit: {self.max_articles}")
                return
            full_url = response.urljoin(link)
            logging.info(f"Following link: {full_url}")
            yield SplashRequest(
                full_url,
                self.parse_article,
                args={'wait': 2},
            )

    def parse_article(self, response):
        if self.article_count >= self.max_articles:
            return

        logging.info(f"Scraping article: {response.url}")
        if 'Gaza' in response.text:
            title = response.css("h1::text").get()
            # Extracting all text within the specified div
            content = ' '.join(response.css('div[data-component="text-block"] p::text').getall())
            logging.info(f"Found relevant article: {title}")
            self.article_count += 1  # Increment the article counter
            yield {
                "title": title,
                "url": response.url,
                "content": content,
            }
        else:
            logging.debug(f"Article does not contain 'Gaza': {response.url}")
