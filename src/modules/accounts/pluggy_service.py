# src/modules/accounts/pluggy_service.py
import os
from typing import Any, cast

import httpx


class PluggyService:
    """Service for integrating with Pluggy Open Finance API."""

    def __init__(self):
        self.api_key = os.getenv("PLUGGY_API_KEY")
        self.api_secret = os.getenv("PLUGGY_API_SECRET")
        self.base_url = "https://api.pluggy.ai"
        self._access_token: str | None = None

    async def _get_access_token(self) -> str:
        """Get or refresh Pluggy API access token."""
        if self._access_token:
            return self._access_token

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/auth",
                    json={
                        "clientId": self.api_key,
                        "clientSecret": self.api_secret,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                from src.core.exceptions import UnauthorizedError
                raise UnauthorizedError(message="Failed to authenticate with Pluggy") from exc

            data = response.json()
            self._access_token = data.get("apiKey")
            assert self._access_token is not None, "Pluggy did not return an apiKey"
            return self._access_token

    async def get_connectors(self) -> list[dict[str, Any]]:
        """Get available bank connectors."""
        token = await self._get_access_token()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/connectors",
                headers={"X-API-KEY": token},
                timeout=30.0,
            )
            response.raise_for_status()
            return cast(list[dict[str, Any]], response.json().get("results", []))

    async def create_connect_token(
        self,
        connector_id: str,
        user_id: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a connect token for the widget."""
        token = await self._get_access_token()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/connect_token",
                headers={"X-API-KEY": token},
                json={
                    "connectorId": connector_id,
                    "user": user_id,
                    "options": options or {},
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def get_item(self, item_id: str) -> dict[str, Any]:
        """Get item details by ID."""
        token = await self._get_access_token()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/items/{item_id}",
                headers={"X-API-KEY": token},
                timeout=30.0,
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def get_accounts(self, item_id: str) -> list[dict[str, Any]]:
        """Get all accounts for an item."""
        token = await self._get_access_token()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/accounts",
                headers={"X-API-KEY": token},
                params={"item": item_id},
                timeout=30.0,
            )
            response.raise_for_status()
            return cast(list[dict[str, Any]], response.json().get("results", []))

    async def get_transactions(
        self,
        account_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get transactions for an account."""
        token = await self._get_access_token()
        params = {"account": account_id}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/transactions",
                headers={"X-API-KEY": token},
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return cast(list[dict[str, Any]], response.json().get("results", []))


pluggy_service = PluggyService()
