import threading
from datetime import datetime

import requests


class Clock:
    def __init__(self, computer):
        self.computer = computer

    def schedule(self, dt, message):
        # Calculate the delay in seconds
        delay = (dt - datetime.now()).total_seconds()

        # Create a timer
        timer = threading.Timer(delay, self.send_message, args=[message])

        # Start the timer
        timer.start()

    def send_message(self, message):
        # Send the message to the websocket endpoint
        requests.post("http://localhost:8080", data=message)
