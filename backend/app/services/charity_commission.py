"""Charity Commission API integration service."""
import asyncio
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
import structlog

logger = structlog.get_logger()


def api_log(msg: str, charity_number: str = "", level: str = "DEBUG"):
    """Log API calls for debugging."""
    timestamp = datetime.utcnow().isoformat()
    context = f"[charity={charity_number}] " if charity_number else ""
    formatted = f"[{level}] [{timestamp}] [CharityAPI] {context}{msg}"
    print(formatted, file=sys.stdout, flush=True)


class CharityCommissionService:
    """Service for interacting with the Charity Commission API.
    
    API Documentation: https://api-portal.charitycommission.gov.uk/
    
    Available endpoints:
    - /charityRegNumber/{regNumber}/{suffix} - Get charity by registration number
    - /charityDetails/{regNumber}/{suffix} - Get detailed charity info
    """
    
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
    
    async def search_charities(
        self,
        search_term: str,
        status: Optional[str] = None,
        page: int = 0,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """
        Search for charities by name.
        
        Note: The Charity Commission API doesn't have a direct name search endpoint.
        We use mock data with known charity mappings for name-based searches.
        For exact charity number lookups, use get_charity_by_number().
        
        Args:
            search_term: Name or keyword to search
            status: Filter by status (registered, removed)
            page: Page number (0-indexed)
            page_size: Number of results per page
        
        Returns:
            Dict containing search results
        """
        # First, check if search term contains a charity number
        extracted_number = self.extract_charity_number(search_term)
        if extracted_number:
            charity = await self.get_charity_by_number(extracted_number)
            if charity:
                return {"charities": [charity]}
        
        # Use name-based lookup with known charity mappings
        return self._get_search_results_by_name(search_term)
    
    def _get_search_results_by_name(self, search_term: str) -> Dict[str, Any]:
        """Get search results by matching charity names."""
        # Known charity data for common searches
        known_charities = {
            "british red cross": {"charityNumber": "220949", "charityName": "THE BRITISH RED CROSS SOCIETY", "registrationStatus": "Registered"},
            "red cross": {"charityNumber": "220949", "charityName": "THE BRITISH RED CROSS SOCIETY", "registrationStatus": "Registered"},
            "oxfam": {"charityNumber": "202918", "charityName": "OXFAM", "registrationStatus": "Registered"},
            "cancer research uk": {"charityNumber": "1089464", "charityName": "CANCER RESEARCH UK", "registrationStatus": "Registered"},
            "cancer research": {"charityNumber": "1089464", "charityName": "CANCER RESEARCH UK", "registrationStatus": "Registered"},
            "nspcc": {"charityNumber": "216401", "charityName": "NATIONAL SOCIETY FOR THE PREVENTION OF CRUELTY TO CHILDREN", "registrationStatus": "Registered"},
            "save the children": {"charityNumber": "213890", "charityName": "SAVE THE CHILDREN INTERNATIONAL", "registrationStatus": "Registered"},
            "barnardo's": {"charityNumber": "216250", "charityName": "BARNARDO'S", "registrationStatus": "Registered"},
            "barnardos": {"charityNumber": "216250", "charityName": "BARNARDO'S", "registrationStatus": "Registered"},
            "marie curie": {"charityNumber": "207994", "charityName": "MARIE CURIE", "registrationStatus": "Registered"},
            "macmillan cancer support": {"charityNumber": "261017", "charityName": "MACMILLAN CANCER SUPPORT", "registrationStatus": "Registered"},
            "macmillan": {"charityNumber": "261017", "charityName": "MACMILLAN CANCER SUPPORT", "registrationStatus": "Registered"},
            "age uk": {"charityNumber": "1128267", "charityName": "AGE UK", "registrationStatus": "Registered"},
            "shelter": {"charityNumber": "263710", "charityName": "SHELTER, NATIONAL CAMPAIGN FOR HOMELESS PEOPLE LIMITED", "registrationStatus": "Registered"},
            "rspca": {"charityNumber": "219099", "charityName": "ROYAL SOCIETY FOR THE PREVENTION OF CRUELTY TO ANIMALS", "registrationStatus": "Registered"},
            "rspb": {"charityNumber": "207076", "charityName": "ROYAL SOCIETY FOR THE PROTECTION OF BIRDS", "registrationStatus": "Registered"},
            "wwf": {"charityNumber": "1081247", "charityName": "WWF-UK", "registrationStatus": "Registered"},
            "world wildlife fund": {"charityNumber": "1081247", "charityName": "WWF-UK", "registrationStatus": "Registered"},
            "unicef": {"charityNumber": "1072612", "charityName": "THE UNITED KINGDOM COMMITTEE FOR UNICEF", "registrationStatus": "Registered"},
            "mind": {"charityNumber": "219830", "charityName": "MIND", "registrationStatus": "Registered"},
            "samaritans": {"charityNumber": "219432", "charityName": "SAMARITANS", "registrationStatus": "Registered"},
            "mencap": {"charityNumber": "222377", "charityName": "ROYAL MENCAP SOCIETY", "registrationStatus": "Registered"},
            "scope": {"charityNumber": "208231", "charityName": "SCOPE", "registrationStatus": "Registered"},
            "actionaid": {"charityNumber": "274467", "charityName": "ACTIONAID", "registrationStatus": "Registered"},
            "christian aid": {"charityNumber": "1105851", "charityName": "CHRISTIAN AID", "registrationStatus": "Registered"},
            "wateraid": {"charityNumber": "288701", "charityName": "WATERAID", "registrationStatus": "Registered"},
            "tearfund": {"charityNumber": "265464", "charityName": "TEARFUND", "registrationStatus": "Registered"},
        }
        
        search_lower = search_term.lower().strip()
        results = []
        seen_numbers = set()
        
        # Exact match first
        if search_lower in known_charities:
            charity = known_charities[search_lower]
            results.append(charity)
            seen_numbers.add(charity["charityNumber"])
        
        # Partial matches
        for key, charity in known_charities.items():
            if charity["charityNumber"] not in seen_numbers:
                if search_lower in key or key in search_lower:
                    results.append(charity)
                    seen_numbers.add(charity["charityNumber"])
        
        # Word-based matches
        if not results:
            for key, charity in known_charities.items():
                if charity["charityNumber"] not in seen_numbers:
                    if any(word in key for word in search_lower.split() if len(word) > 3):
                        results.append(charity)
                        seen_numbers.add(charity["charityNumber"])
        
        logger.info("Name search results", search_term=search_term, results_count=len(results))
        return {"charities": results}
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_charity_by_number(self, charity_number: str) -> Optional[Dict[str, Any]]:
        """
        Get charity details by registration number.
        
        Args:
            charity_number: Charity registration number
        
        Returns:
            Dict containing charity details or None if not found
        """
        normalized = self.normalize_charity_number(charity_number)
        api_log(f"get_charity_by_number: looking up charity #{normalized}", charity_number=normalized)
        
        # Check if API key is configured
        if not self.api_key:
            api_log("API key not configured - cannot fetch charity details", charity_number=normalized, level="WARNING")
            logger.warning("Charity Commission API key not configured")
            return None
        
        client = await self.get_client()
        
        try:
            # Use charityDetails endpoint for full info
            start_time = datetime.utcnow()
            api_log(f"Calling API: GET /charityDetails/{normalized}/0", charity_number=normalized)
            response = await client.get(f"/charityDetails/{normalized}/0")
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            if response.status_code == 404:
                api_log(f"API returned 404 (not found) in {duration:.2f}s", charity_number=normalized)
                return None
            
            response.raise_for_status()
            data = response.json()
            api_log(f"API SUCCESS in {duration:.2f}s: charity_name='{data.get('charity_name', 'N/A')}'", charity_number=normalized)
            
            # Convert API response to our expected format
            return {
                "charityNumber": str(data.get("reg_charity_number", normalized)),
                "charityName": data.get("charity_name"),
                "registrationStatus": "Registered" if data.get("reg_status") == "R" else "Removed",
                "registrationDate": data.get("date_of_registration"),
                "removalDate": data.get("date_of_removal"),
                "charityType": data.get("charity_type"),
                "activities": data.get("activities"),
                "contact": {
                    "email": data.get("email"),
                    "phone": data.get("phone"),
                    "web": data.get("web"),
                    "addressLine1": data.get("address_line_one"),
                    "addressLine2": data.get("address_line_two"),
                    "addressLine3": data.get("address_line_three"),
                    "addressLine4": data.get("address_line_four"),
                    "postcode": data.get("address_post_code"),
                },
                "latestIncome": data.get("latest_income"),
                "latestExpenditure": data.get("latest_expenditure"),
                "latestFinYearStart": data.get("latest_acc_fin_year_start_date"),
                "latestFinYearEnd": data.get("latest_acc_fin_year_end_date"),
                "companyNumber": data.get("charity_co_reg_number"),
                "raw_data": data,
            }
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
        if not self.api_key:
            return []
            
        client = await self.get_client()
        normalized = self.normalize_charity_number(charity_number)
        
        try:
            response = await client.get(f"/charityTrustees/{normalized}/0")
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            logger.error("Charity Commission API error", status_code=e.response.status_code, error=str(e))
            return []
        except Exception as e:
            logger.error("Charity Commission API error", error=str(e))
            return []
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_charity_accounts(self, charity_number: str) -> List[Dict[str, Any]]:
        """
        Get financial accounts for a charity.
        
        Args:
            charity_number: Charity registration number
        
        Returns:
            List of account records
        """
        # Financial data is included in charityDetails response
        return []
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_charity_subsidiaries(self, charity_number: str) -> List[Dict[str, Any]]:
        """
        Get subsidiary undertakings for a charity.
        
        Args:
            charity_number: Charity registration number
        
        Returns:
            List of subsidiary records
        """
        if not self.api_key:
            return []
            
        client = await self.get_client()
        normalized = self.normalize_charity_number(charity_number)
        
        try:
            response = await client.get(f"/charitySubsidiaries/{normalized}/0")
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            logger.error("Charity Commission API error", status_code=e.response.status_code, error=str(e))
            return []
        except Exception as e:
            logger.error("Charity Commission API error", error=str(e))
            return []
    
    async def get_full_charity_details(self, charity_number: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive charity details including trustees and subsidiaries.
        
        Args:
            charity_number: Charity registration number
        
        Returns:
            Dict containing full charity details
        """
        # Fetch all data concurrently
        charity_data, trustees, subsidiaries = await asyncio.gather(
            self.get_charity_by_number(charity_number),
            self.get_charity_trustees(charity_number),
            self.get_charity_subsidiaries(charity_number),
            return_exceptions=True,
        )
        
        if charity_data is None or isinstance(charity_data, Exception):
            return None
        
        # Add related data
        charity_data["trustees"] = trustees if not isinstance(trustees, Exception) else []
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
            "latest_income": data.get("latestIncome"),
            "latest_expenditure": data.get("latestExpenditure"),
            "financial_year_end": None,
            "trustees": [],
            "subsidiaries": [],
        }
        
        # Parse dates
        if data.get("registrationDate"):
            try:
                date_str = data["registrationDate"]
                if isinstance(date_str, str):
                    parsed["registration_date"] = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
            except (ValueError, TypeError):
                pass
        
        if data.get("removalDate"):
            try:
                date_str = data["removalDate"]
                if isinstance(date_str, str):
                    parsed["removal_date"] = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
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
        
        # Parse financial year end
        if data.get("latestFinYearEnd"):
            try:
                date_str = data["latestFinYearEnd"]
                if isinstance(date_str, str):
                    parsed["financial_year_end"] = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
            except (ValueError, TypeError):
                pass
        
        # Parse trustees
        trustees = data.get("trustees", [])
        parsed["trustees"] = [
            {
                "name": t.get("trustee_name") or t.get("trusteeName"),
                "id": t.get("trustee_id") or t.get("trusteeId"),
            }
            for t in trustees if isinstance(t, dict)
        ]
        
        # Parse subsidiaries
        subsidiaries = data.get("subsidiaries", [])
        parsed["subsidiaries"] = [
            {
                "name": s.get("subsidiary_name") or s.get("subsidiaryName"),
                "company_number": s.get("company_number") or s.get("companyNumber"),
            }
            for s in subsidiaries if isinstance(s, dict)
        ]
        
        return parsed
