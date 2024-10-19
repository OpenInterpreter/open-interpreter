import threading
import time

import html2text
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager


class Browser:
    def __init__(self, computer):
        self.computer = computer
        self._driver = None

    @property
    def driver(self, headless=False):
        if self._driver is None:
            self.setup(headless)
        return self._driver

    @driver.setter
    def driver(self, value):
        self._driver = value

    def search(self, query):
        """
        Searches the web for the specified query and returns the results.
        """
        response = requests.get(
            f'{self.computer.api_base.strip("/")}/browser/search',
            params={"query": query},
        )
        return response.json()["result"]

    def fast_search(self, query):
        """
        Searches the web for the specified query and returns the results.
        """

        # Start the request in a separate thread
        response_thread = threading.Thread(
            target=lambda: setattr(
                threading.current_thread(),
                "response",
                requests.get(
                    f'{self.computer.api_base.strip("/")}/browser/search',
                    params={"query": query},
                ),
            )
        )
        response_thread.start()

        # Perform the Google search
        self.search_google(query, delays=False)

        # Wait for the request to complete and get the result
        response_thread.join()
        response = response_thread.response

        return response.json()["result"]

    def setup(self, headless):
        try:
            self.service = Service(ChromeDriverManager().install())
            self.options = webdriver.ChromeOptions()
            # Run Chrome in headless mode
            if headless:
                self.options.add_argument("--headless")
                self.options.add_argument("--disable-gpu")
                self.options.add_argument("--no-sandbox")
            self._driver = webdriver.Chrome(service=self.service, options=self.options)
        except Exception as e:
            print(f"An error occurred while setting up the WebDriver: {e}")
            self._driver = None

    def go_to_url(self, url):
        """Navigate to a URL"""
        self.driver.get(url)
        time.sleep(1)

    def search_google(self, query, delays=True):
        """Perform a Google search"""
        self.driver.get("https://www.perplexity.ai")
        # search_box = self.driver.find_element(By.NAME, 'q')
        # search_box.send_keys(query)
        # search_box.send_keys(Keys.RETURN)
        body = self.driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.COMMAND + "k")
        time.sleep(0.5)
        active_element = self.driver.switch_to.active_element
        active_element.send_keys(query)
        active_element.send_keys(Keys.RETURN)
        if delays:
            time.sleep(3)

    def analyze_page(self, intent):
        """Extract HTML, list interactive elements, and analyze with AI"""
        html_content = self.driver.page_source
        text_content = html2text.html2text(html_content)

        # text_content = text_content[:len(text_content)//2]

        elements = (
            self.driver.find_elements(By.TAG_NAME, "a")
            + self.driver.find_elements(By.TAG_NAME, "button")
            + self.driver.find_elements(By.TAG_NAME, "input")
            + self.driver.find_elements(By.TAG_NAME, "select")
        )

        elements_info = [
            {
                "id": idx,
                "text": elem.text,
                "attributes": elem.get_attribute("outerHTML"),
            }
            for idx, elem in enumerate(elements)
        ]

        ai_query = f"""
        Below is the content of the current webpage along with interactive elements. 
        Given the intent "{intent}", please extract useful information and provide sufficient details 
        about interactive elements, focusing especially on those pertinent to the provided intent.
        
        If the information requested by the intent "{intent}" is present on the page, simply return that.

        If not, return the top 10 most relevant interactive elements in a concise, actionable format, listing them on separate lines
        with their ID, a description, and their possible action.

        Do not hallucinate.

        Page Content:
        {text_content}
        
        Interactive Elements:
        {elements_info}
        """

        # response = self.computer.ai.chat(ai_query)

        # screenshot = self.driver.get_screenshot_as_base64()
        # old_model = self.computer.interpreter.llm.model
        # self.computer.interpreter.llm.model = "gpt-4o-mini"
        # response = self.computer.ai.chat(ai_query, base64=screenshot)
        # self.computer.interpreter.llm.model = old_model

        old_model = self.computer.interpreter.llm.model
        self.computer.interpreter.llm.model = "gpt-4o-mini"
        response = self.computer.ai.chat(ai_query)
        self.computer.interpreter.llm.model = old_model

        print(response)
        print(
            "Please now utilize this information or interact with the interactive elements provided to answer the user's query."
        )

    def quit(self):
        """Close the browser"""
        self.driver.quit()
