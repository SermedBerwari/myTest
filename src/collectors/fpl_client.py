"""
FPL API Client

Provides a reusable client for communicating with the official
Fantasy Premier League API.

Current project scope:
- bootstrap-static
- fixtures
- player summary
- live gameweek

This module is responsible only for API communication.
It does NOT save data to the database or perform ML processing.
"""

from __future__ import annotations

import time
from typing import Any

import requests


class FPLAPIError(Exception):
    """Raised when the FPL API request fails."""


class FPLClient:
    """Client for the official Fantasy Premier League API."""

    BASE_URL = "https://fantasy.premierleague.com/api"

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "FPL-AI-Agent/1.0 "
                    "(local research and prediction project)"
                ),
                "Accept": "application/json",
            }
        )

    def _get(self, endpoint: str) -> Any:
        """
        Perform a GET request against the FPL API.

        Includes retry handling for temporary failures.
        """

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                )

                response.raise_for_status()

                try:
                    return response.json()
                except ValueError as exc:
                    raise FPLAPIError(
                        f"Invalid JSON returned by FPL API: {url}"
                    ) from exc

            except requests.exceptions.RequestException as exc:
                last_error = exc

                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        raise FPLAPIError(
            f"FPL API request failed after "
            f"{self.max_retries} attempts: {url}"
        ) from last_error

    def get_bootstrap(self) -> dict[str, Any]:
        """
        Get the main FPL dataset.

        Endpoint:
            /api/bootstrap-static/
        """

        data = self._get("bootstrap-static/")

        if not isinstance(data, dict):
            raise FPLAPIError(
                "bootstrap-static returned an unexpected data structure."
            )

        return data

    def get_fixtures(self) -> list[dict[str, Any]]:
        """
        Get all FPL fixtures.

        Endpoint:
            /api/fixtures/
        """

        data = self._get("fixtures/")

        if not isinstance(data, list):
            raise FPLAPIError(
                "fixtures endpoint returned an unexpected data structure."
            )

        return data

    def get_player_summary(self, player_id: int) -> dict[str, Any]:
        """
        Get detailed history and fixture information for one player.

        Endpoint:
            /api/element-summary/{player_id}/
        """

        if not isinstance(player_id, int) or player_id <= 0:
            raise ValueError(
                "player_id must be a positive integer."
            )

        data = self._get(f"element-summary/{player_id}/")

        if not isinstance(data, dict):
            raise FPLAPIError(
                "Player summary returned an unexpected data structure."
            )

        return data

    def get_live_gameweek(
        self,
        gameweek: int,
    ) -> dict[str, Any]:
        """
        Get live statistics for a gameweek.

        Endpoint:
            /api/event/{gameweek}/live/
        """

        if not isinstance(gameweek, int) or gameweek <= 0:
            raise ValueError(
                "gameweek must be a positive integer."
            )

        data = self._get(f"event/{gameweek}/live/")

        if not isinstance(data, dict):
            raise FPLAPIError(
                "Live gameweek endpoint returned an "
                "unexpected data structure."
            )

        return data

    def close(self) -> None:
        """Close the underlying HTTP session."""

        self.session.close()

    def __enter__(self) -> "FPLClient":
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.close()