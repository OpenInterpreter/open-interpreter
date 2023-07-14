from __future__ import annotations

import os


# Timeout for HTTP requests using the requests library.
REQUESTS_TIMEOUT = int(os.getenv("POETRY_REQUESTS_TIMEOUT", 15))

RETRY_AFTER_HEADER = "retry-after"

# Server response codes to retry requests on.
STATUS_FORCELIST = [429, 500, 501, 502, 503, 504]
