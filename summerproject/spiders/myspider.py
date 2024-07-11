import scrapy
from scrapy_splash import SplashRequest
import logging

class BbcSpider(scrapy.Spider):
    name = "bbc"
    start_urls = ["https://www.bbc.com/news"]
    max_articles = 10  # Define the maximum number of articles to crawl
    article_count = 0  # Initialize the article counter

    def start_requests(self):
        for url in self.start_urls:
            yield SplashRequest(
                url,
                self.parse,
                args={'wait': 2},
            )

    def parse(self, response):
        logging.info(f"Processing URL: {response.url}")
        # Adjust the CSS selector based on BBC News HTML structure
        article_links = response.css('a[href*="/news/articles/"]::attr(href)').getall()
        logging.info(f"Found {len(article_links)} article links")

        for link in article_links:
            if self.article_count >= self.max_articles:
                logging.info(f"Reached max articles limit: {self.max_articles}")
                break
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
