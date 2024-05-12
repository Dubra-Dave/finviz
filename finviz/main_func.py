from datetime import datetime
import traceback

from lxml import etree

from finviz.helper_functions.request_functions import http_request_get
from finviz.helper_functions.scraper_functions import get_table

STOCK_URL = "https://finviz.com/quote.ashx"
NEWS_URL = "https://finviz.com/news.ashx"
CRYPTO_URL = "https://finviz.com/crypto_performance.ashx"
STOCK_PAGE = {}


def get_page(ticker):
    #DE: It is bad practice to store things in a global variable like this.
    # STOCK_PAGE should be a class - This is a to-do
    global STOCK_PAGE

    if ticker not in STOCK_PAGE:
        STOCK_PAGE[ticker], _ = http_request_get(
            url=STOCK_URL, payload={"t": ticker}, parse=True
        )


def get_stock(ticker):
    """
    Returns a dictionary containing stock data.

    :param ticker: stock symbol
    :type ticker: str
    :return dict
    """

    get_page(ticker)
    page_parsed = STOCK_PAGE[ticker]

    title = page_parsed.cssselect('div[class="fv-container py-2.5"]')[0]
    data = {}
    data["Ticker"] = title.cssselect('h1[class="js-recent-quote-ticker quote-header_ticker-wrapper_ticker"]')[
        0].text_content().strip()
    try:
        company_details = title.cssselect('h2[class="quote-header_ticker-wrapper_company text-xl"]')[0]
    except IndexError:
        company_details = title.cssselect('h2[class="quote-header_ticker-wrapper_company"]')[0]

    data["Company"] = company_details.text_content().strip()
    company_link = company_details.cssselect('a[class="tab-link block truncate"]')[0].attrib["href"]
    data["Website"] = company_link if company_link.startswith("http") else None
    keys = ["Sector", "Industry", "Country", "Exchange"]
    fields = [f.text_content() for f in title.cssselect('a[class="tab-link"]')]
    data.update(dict(zip(keys, fields)))

    excluded_strings = ['\r', '\n', '\r\n    ', '\r\n', 'Trades']
    all_rows = [
        [item for item in row.xpath("td//text()") if item not in excluded_strings]
        for row in page_parsed.cssselect('tr[class="table-dark-row"]')
    ]

    for row in all_rows:
        for column in range(0, len(row) - 1):
            if column % 2 == 0:
                data[row[column]] = row[column + 1]

    return data


def get_insider(ticker):
    """
    Returns a list of dictionaries containing all recent insider transactions.

    :param ticker: stock symbol
    :return: list
    """
    get_page(ticker)
    page_parsed = STOCK_PAGE[ticker]
    outer_table = page_parsed.cssselect('table[class="body-table styled-table-new is-rounded p-0 mt-2"]')
    data = []

    try:
        table = outer_table[0]
        headers = table[0].xpath(".//th//text()")
        data = [dict(zip(
            headers,
            [etree.tostring(elem, method="text", encoding="unicode") for elem in row]
        )) for row in table[1:]]
    except Exception as e:
        pass
        traceback.print_exception(type(e), e, e.__traceback__)
    return data

def get_news(ticker):
    """
    Returns a list of sets containing news headline and url

    :param ticker: stock symbol
    :return: list
    """

    get_page(ticker)
    page_parsed = STOCK_PAGE[ticker]
    news_table = page_parsed.cssselect('table[id="news-table"]')

    if len(news_table) == 0:
        return []

    rows = news_table[0].xpath("./tr[not(@id)]")

    results = []
    date = None
    for row in rows:
        try:
            results.append((
                row.xpath("./td")[1].cssselect('a[class="tab-link-news"]')[0].xpath("text()")[0],
                row.xpath("./td")[1].cssselect('a[class="tab-link-news"]')[0].get("href"),
                row.xpath("./td")[1].cssselect('div[class="news-link-right"] span')[0].xpath("text()")[0][1:]
            ))
        except Exception as e:
            pass
            traceback.print_exception(type(e), e, e.__traceback__)
    return results


def get_all_news():
    """
    Returns a list of sets containing time, headline and url
    :return: list
    """
    page_parsed, _ = http_request_get(url=NEWS_URL, parse=True)
    all_dates = [
        row.text_content() for row in page_parsed.cssselect('td.news_date-cell')
    ]
    all_headlines = [
        row.text_content() for row in page_parsed.cssselect('a.tab-link')
    ]
    all_links = [
        row.get("href") for row in page_parsed.cssselect('a.tab-link')
    ]
    return list(zip(all_dates, all_headlines, all_links))


def get_crypto(pair):
    """

    :param pair: crypto pair
    :return: dictionary
    """

    page_parsed, _ = http_request_get(url=CRYPTO_URL, parse=True)
    page_html, _ = http_request_get(url=CRYPTO_URL, parse=False)
    crypto_headers = page_parsed.cssselect('tr[valign="middle"]')[0].xpath("td//text()")
    crypto_table_data = get_table(page_html, crypto_headers)

    return crypto_table_data[pair]


def get_analyst_price_targets(ticker, last_ratings=5):
    """
    Returns a list of dictionaries containing all analyst ratings and Price targets
     - if any of 'price_from' or 'price_to' are not available in the DATA, then those values are set to default 0
    :param ticker: stock symbol
    :param last_ratings: most recent ratings to pull
    :return: list
    """

    analyst_price_targets = []

    try:
        get_page(ticker)
        page_parsed = STOCK_PAGE[ticker]
        table = page_parsed.cssselect(
            'table[class="js-table-ratings fullview-ratings-outer"]'
        )[0]

        for row in table:
            rating = row.xpath("td//text()")
            rating = [val.replace("→", "->").replace("$", "") for val in rating if val != "\n"]
            rating[0] = datetime.strptime(rating[0], "%b-%d-%y").strftime("%Y-%m-%d")

            data = {
                "date": rating[0],
                "category": rating[1],
                "analyst": rating[2],
                "rating": rating[3],
            }
            if len(rating) == 5:
                if "->" in rating[4]:
                    rating.extend(rating[4].replace(" ", "").split("->"))
                    del rating[4]
                    data["target_from"] = float(rating[4])
                    data["target_to"] = float(rating[5])
                else:
                    data["target"] = float(rating[4])

            analyst_price_targets.append(data)
    except Exception as e:
        pass

    return analyst_price_targets[:last_ratings]
