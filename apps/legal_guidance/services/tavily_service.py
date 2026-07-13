import requests
from django.conf import settings


class TavilyService:
    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY
        self.search_url = settings.TAVILY_SEARCH_URL

    def search(self, query: str, max_results: int = 3) -> list[dict]:
        if not settings.TAVILY_ENABLED:
            return []

        if not self.api_key:
            return []

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_domains": [
                "nacc.gov.ph",
                "dswd.gov.ph",
                "officialgazette.gov.ph",
                "lawphil.net",
            ],
        }

        response = requests.post(
            self.search_url,
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("results", [])