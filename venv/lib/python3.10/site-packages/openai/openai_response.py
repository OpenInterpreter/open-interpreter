from typing import Optional


class OpenAIResponse:
    def __init__(self, data, headers):
        self._headers = headers
        self.data = data

    @property
    def request_id(self) -> Optional[str]:
        return self._headers.get("request-id")

    @property
    def retry_after(self) -> Optional[int]:
        try:
            return int(self._headers.get("retry-after"))
        except TypeError:
            return None

    @property
    def operation_location(self) -> Optional[str]:
        return self._headers.get("operation-location")

    @property
    def organization(self) -> Optional[str]:
        return self._headers.get("OpenAI-Organization")

    @property
    def response_ms(self) -> Optional[int]:
        h = self._headers.get("Openai-Processing-Ms")
        return None if h is None else round(float(h))
