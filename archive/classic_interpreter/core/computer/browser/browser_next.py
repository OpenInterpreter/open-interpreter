"""
Eventually we should own the browser
"""

import concurrent.futures
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


def setup_driver():
    # Setup Chrome options to speed up the browser
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("start-maximized")
    options.add_argument("disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-images")  # Disable images for faster loading
    driver_path = "path_to_your_chromedriver"
    driver = webdriver.Chrome(executable_path=driver_path, options=options)
    return driver


def fetch_page_text(url):
    driver = setup_driver()
    driver.get(url)
    text = driver.find_element(By.TAG_NAME, "body").text
    driver.quit()
    return text


def get_google_search_results(query):
    driver = setup_driver()
    driver.get("http://www.google.com")
    search_box = driver.find_element(By.NAME, "q")
    search_box.send_keys(query)
    search_box.send_keys(Keys.RETURN)
    time.sleep(2)  # Allow page to load

    results = []
    search_results = driver.find_elements(By.CSS_SELECTOR, "div.g")[
        :5
    ]  # Limit to top 5 results

    for result in search_results:
        title_element = result.find_element(By.CSS_SELECTOR, "h3")
        title = title_element.text
        link = result.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
        results.append({"title": title, "link": link})

    driver.quit()
    return results


# Main execution block
search_query = "selenium automation tools"
results = get_google_search_results(search_query)

# Use concurrent futures to fetch text content in parallel
with concurrent.futures.ThreadPoolExecutor() as executor:
    future_to_url = {
        executor.submit(fetch_page_text, result["link"]): result for result in results
    }
    for future in concurrent.futures.as_completed(future_to_url):
        url = future_to_url[future]
        try:
            page_text = future.result()
            print(
                f"Title: {url['title']}\nURL: {url['link']}\nText: {page_text[:500]}...\n"
            )  # Print the first 500 characters
        except Exception as exc:
            print(f'{url["link"]} generated an exception: {exc}')
