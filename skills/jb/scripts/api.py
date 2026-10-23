import json
import time
import urllib.error
import urllib.request

import config


class Key:
    def __init__(self, absence, section, key):
        self.absence = absence
        self.section = section
        self.key = key

    def __call__(self):
        return config.optional(self.section, self.key)

    def message(self, consequence=""):
        return f"{self.absence}{consequence}. " + config.MissingConfig(self.section, self.key).message()

def read(url, headers=None, timeout=30, attempts=5, codes=(429, 500, 503, 504)):
    query = urllib.request.Request(url, headers=headers or {})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(query, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code not in codes or attempt == attempts - 1:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == attempts - 1:
                raise
        time.sleep(1 + attempt)
