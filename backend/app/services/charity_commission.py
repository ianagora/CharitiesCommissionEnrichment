"""Charity Commission API integration service."""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
import structlog

logger = structlog.get_logger()


class CharityCommissionService:
    """Service for interacting with the Charity Commission API."""
    
    BASE_URL = settings.CHARITY_COMMISSION_API_BASE_URL
    
    def __init__(self):
        self.api_key = settings.CHARITY_COMMISSION_API_KEY
        self._client: Optional[httpx.AsyncClient] = None
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Accept": "application/json",
                "User-Agent": "CharityDataEnrichmentPlatform/1.0",
            }
            if self.api_key:
                headers["Ocp-Apim-Subscription-Key"] = self.api_key
            
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=headers,
                timeout=30.0,
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    @staticmethod
    def normalize_charity_number(charity_number: str) -> str:
        """Normalize charity number to standard format."""
        # Remove any non-alphanumeric characters
        normalized = re.sub(r'[^a-zA-Z0-9]', '', charity_number.strip())
        return normalized.upper()
    
    @staticmethod
    def extract_charity_number(text: str) -> Optional[str]:
        """Extract charity number from text."""
        # Common patterns: 123456, 1234567, SC012345, NI12345
        patterns = [
            r'\b(\d{6,8})\b',  # Standard charity number
            r'\b(SC\d{5,6})\b',  # Scottish charity
            r'\b(NI\d{5,6})\b',  # Northern Ireland charity
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def search_charities(
        self,
        search_term: str,
        status: Optional[str] = None,
        page: int = 0,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """
        Search for charities by name or other criteria.
        
        Args:
            search_term: Name or keyword to search
            status: Filter by status (registered, removed)
            page: Page number (0-indexed)
            page_size: Number of results per page
        
        Returns:
            Dict containing search results
        """
        client = await self.get_client()
        
        params = {
            "searchText": search_term,
            "page": page,
            "pageSize": page_size,
        }
        if status:
            params["status"] = status
        
        try:
            response = await client.get("/allcharities", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Charity Commission API error", status_code=e.response.status_code, error=str(e))
            raise
        except Exception as e:
            logger.error("Charity Commission API error", error=str(e))
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_charity_by_number(self, charity_number: str) -> Optional[Dict[str, Any]]:
        """
        Get charity details by registration number.
        
        Args:
            charity_number: Charity registration number
        
        Returns:
            Dict containing charity details or None if not found
        """
        client = await self.get_client()
        normalized = self.normalize_charity_number(charity_number)
        
        try:
            response = await client.get(f"/charities/{normalized}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error("Charity Commission API error", status_code=e.response.status_code, error=str(e))
            raise
        except Exception as e:
            logger.error("Charity Commission API error", error=str(e))
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_charity_trustees(self, charity_number: str) -> List[Dict[str, Any]]:
        """
        Get trustees for a charity.
        
        Args:
            charity_number: Charity registration number
        
        Returns:
            List of trustee records
        """
        client = await self.get_client()
        normalized = self.normalize_charity_number(charity_number)
        
        try:
            response = await client.get(f"/charities/{normalized}/trustees")
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            logger.error("Charity Commission API error", status_code=e.response.status_code, error=str(e))
            raise
        except Exception as e:
            logger.error("Charity Commission API error", error=str(e))
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_charity_accounts(self, charity_number: str) -> List[Dict[str, Any]]:
        """
        Get financial accounts for a charity.
        
        Args:
            charity_number: Charity registration number
        
        Returns:
            List of account records
        """
        client = await self.get_client()
        normalized = self.normalize_charity_number(charity_number)
        
        try:
            response = await client.get(f"/charities/{normalized}/accounts")
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            logger.error("Charity Commission API error", status_code=e.response.status_code, error=str(e))
            raise
        except Exception as e:
            logger.error("Charity Commission API error", error=str(e))
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_charity_subsidiaries(self, charity_number: str) -> List[Dict[str, Any]]:
        """
        Get subsidiary undertakings for a charity.
        
        Args:
            charity_number: Charity registration number
        
        Returns:
            List of subsidiary records
        """
        client = await self.get_client()
        normalized = self.normalize_charity_number(charity_number)
        
        try:
            response = await client.get(f"/charities/{normalized}/subsidiaries")
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            logger.error("Charity Commission API error", status_code=e.response.status_code, error=str(e))
            raise
        except Exception as e:
            logger.error("Charity Commission API error", error=str(e))
            raise
    
    async def get_full_charity_details(self, charity_number: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive charity details including trustees and accounts.
        
        Args:
            charity_number: Charity registration number
        
        Returns:
            Dict containing full charity details
        """
        # Fetch all data concurrently
        charity_data, trustees, accounts, subsidiaries = await asyncio.gather(
            self.get_charity_by_number(charity_number),
            self.get_charity_trustees(charity_number),
            self.get_charity_accounts(charity_number),
            self.get_charity_subsidiaries(charity_number),
            return_exceptions=True,
        )
        
        if charity_data is None or isinstance(charity_data, Exception):
            return None
        
        # Add related data
        charity_data["trustees"] = trustees if not isinstance(trustees, Exception) else []
        charity_data["accounts"] = accounts if not isinstance(accounts, Exception) else []
        charity_data["subsidiaries"] = subsidiaries if not isinstance(subsidiaries, Exception) else []
        
        return charity_data
    
    @staticmethod
    def parse_charity_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw API response into standardized format.
        
        Args:
            data: Raw API response
        
        Returns:
            Standardized charity data
        """
        # Extract basic info
        parsed = {
            "charity_number": data.get("charityNumber") or data.get("registeredCharityNumber"),
            "name": data.get("charityName") or data.get("name"),
            "status": data.get("registrationStatus"),
            "registration_date": None,
            "removal_date": None,
            "activities": data.get("activities"),
            "contact_email": None,
            "contact_phone": None,
            "website": None,
            "address": None,
            "latest_income": None,
            "latest_expenditure": None,
            "financial_year_end": None,
            "trustees": [],
            "subsidiaries": [],
        }
        
        # Parse dates
        if data.get("registrationDate"):
            try:
                parsed["registration_date"] = datetime.fromisoformat(
                    data["registrationDate"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        
        if data.get("removalDate"):
            try:
                parsed["removal_date"] = datetime.fromisoformat(
                    data["removalDate"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        
        # Parse contact info
        contact = data.get("contact", {}) or {}
        parsed["contact_email"] = contact.get("email")
        parsed["contact_phone"] = contact.get("phone")
        parsed["website"] = contact.get("web")
        
        # Parse address
        address_parts = []
        for key in ["addressLine1", "addressLine2", "addressLine3", "addressLine4", "postcode"]:
            if contact.get(key):
                address_parts.append(contact[key])
        parsed["address"] = ", ".join(address_parts) if address_parts else None
        
        # Parse financial data from accounts
        accounts = data.get("accounts", [])
        if accounts:
            latest_account = accounts[0]  # Assume sorted by date
            parsed["latest_income"] = latest_account.get("totalGrossIncome")
            parsed["latest_expenditure"] = latest_account.get("totalGrossExpenditure")
            if latest_account.get("financialYearEnd"):
                try:
                    parsed["financial_year_end"] = datetime.fromisoformat(
                        latest_account["financialYearEnd"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass
        
        # Parse trustees
        trustees = data.get("trustees", [])
        parsed["trustees"] = [
            {
                "name": t.get("trusteeName"),
                "id": t.get("trusteeId"),
            }
            for t in trustees
        ]
        
        # Parse subsidiaries
        subsidiaries = data.get("subsidiaries", [])
        parsed["subsidiaries"] = [
            {
                "name": s.get("subsidiaryName"),
                "company_number": s.get("companyNumber"),
            }
            for s in subsidiaries
        ]
        
        return parsed
