"""WIPO Madrid Monitor API client.

WIPO Madrid Monitor provides data on international trademark registrations.
API documentation: https://www.wipo.int/madrid/monitor/en/

Rate limit: 10 requests per minute (official)
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class WIPODesignation:
    """Designation (territory) in international registration."""

    country_code: str
    country_name: Optional[str] = None
    status: Optional[str] = None
    notification_date: Optional[date] = None
    protection_date: Optional[date] = None
    refusal_date: Optional[date] = None


@dataclass
class WIPOTrademarkData:
    """Data extracted from WIPO for an international trademark."""

    international_number: str
    application_number: Optional[str] = None
    trademark_name: Optional[str] = None
    status: Optional[str] = None
    filing_date: Optional[date] = None
    registration_date: Optional[date] = None
    expiration_date: Optional[date] = None
    rights_holder: Optional[str] = None
    rights_holder_country: Optional[str] = None
    icgs_classes: Optional[list[int]] = None
    image_url: Optional[str] = None
    designations: list[WIPODesignation] = field(default_factory=list)
    origin_country: Optional[str] = None
    raw_data: Optional[dict] = None
    error: Optional[str] = None


class WIPOClient:
    """Client for WIPO Madrid Monitor API.

    Uses httpx for async HTTP requests.
    Implements rate limiting to comply with WIPO guidelines.
    """

    # WIPO Madrid Monitor endpoints
    BASE_URL = "https://www3.wipo.int/madrid/monitor/en"
    API_URL = "https://www3.wipo.int/madrid/monitor/api"
    SEARCH_URL = f"{BASE_URL}/search.jsp"
    DETAIL_URL = f"{BASE_URL}/showData.jsp"

    # Rate limiting: requests per minute from settings
    RATE_LIMIT = getattr(settings, 'wipo_rate_limit_per_minute', 10)
    MIN_DELAY = 60.0 / RATE_LIMIT  # Minimum seconds between requests

    def __init__(self):
        self._last_request_time: float = 0
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/html, */*',
                'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            },
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self.MIN_DELAY:
                wait_time = self.MIN_DELAY - elapsed
                logger.debug(f"WIPO rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            self._last_request_time = asyncio.get_event_loop().time()

    async def get_trademark_by_number(
        self,
        international_number: str,
        retries: int = 3
    ) -> WIPOTrademarkData:
        """
        Fetch trademark data from WIPO by international registration number.

        Args:
            international_number: WIPO international registration number
            retries: Number of retry attempts on failure

        Returns:
            WIPOTrademarkData with extracted information
        """
        result = WIPOTrademarkData(international_number=international_number)

        # Clean the number (remove any prefixes/spaces)
        clean_number = re.sub(r'[^0-9]', '', international_number)

        for attempt in range(retries):
            try:
                await self._rate_limit()

                # Try JSON API first
                api_result = await self._fetch_from_api(clean_number)
                if api_result and not api_result.error:
                    return api_result

                # Fallback to HTML scraping
                await self._rate_limit()
                html_result = await self._fetch_from_html(clean_number)
                if html_result:
                    return html_result

                result.error = "Could not fetch data from WIPO"

            except httpx.TimeoutException as e:
                logger.warning(f"Timeout for WIPO {international_number}: {e}")
                result.error = f"Timeout: {e}"
                if attempt < retries - 1:
                    await asyncio.sleep(5)

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error for WIPO {international_number}: {e}")
                result.error = f"HTTP error: {e.response.status_code}"
                if attempt < retries - 1:
                    await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error fetching WIPO {international_number}: {e}")
                result.error = str(e)
                if attempt < retries - 1:
                    await asyncio.sleep(5)

        return result

    async def _fetch_from_api(self, number: str) -> Optional[WIPOTrademarkData]:
        """Try to fetch data from WIPO JSON API."""
        try:
            # WIPO Madrid Monitor API endpoint
            url = f"{self.API_URL}/brands/{number}"

            response = await self._client.get(url)

            if response.status_code == 404:
                return WIPOTrademarkData(
                    international_number=number,
                    error="Trademark not found"
                )

            if response.status_code != 200:
                return None

            data = response.json()
            return self._parse_api_response(number, data)

        except Exception as e:
            logger.debug(f"API fetch failed: {e}")
            return None

    async def _fetch_from_html(self, number: str) -> Optional[WIPOTrademarkData]:
        """Fetch data by scraping HTML page."""
        try:
            url = f"{self.DETAIL_URL}?ID={quote(number)}"

            response = await self._client.get(url)

            if response.status_code != 200:
                return None

            html = response.text

            # Check if trademark exists
            if 'No data found' in html or 'not found' in html.lower():
                return WIPOTrademarkData(
                    international_number=number,
                    error="Trademark not found"
                )

            return self._parse_html_response(number, html)

        except Exception as e:
            logger.debug(f"HTML fetch failed: {e}")
            return None

    def _parse_api_response(self, number: str, data: dict) -> WIPOTrademarkData:
        """Parse JSON API response."""
        result = WIPOTrademarkData(international_number=number)
        result.raw_data = data

        try:
            # Basic info
            result.application_number = data.get('applicationNumber')
            result.trademark_name = data.get('markFeature') or data.get('wordElement')
            result.status = self._normalize_status(data.get('status', ''))

            # Dates
            if data.get('applicationDate'):
                result.filing_date = self._parse_date(data['applicationDate'])
            if data.get('registrationDate'):
                result.registration_date = self._parse_date(data['registrationDate'])
            if data.get('expiryDate'):
                result.expiration_date = self._parse_date(data['expiryDate'])

            # Rights holder
            holders = data.get('holders', [])
            if holders:
                holder = holders[0]
                result.rights_holder = holder.get('name')
                result.rights_holder_country = holder.get('countryCode')

            # Origin country
            result.origin_country = data.get('originCountry')

            # ICGS classes
            classes = data.get('niceClasses', [])
            if classes:
                result.icgs_classes = [int(c) for c in classes if str(c).isdigit()]

            # Image URL
            if data.get('markImageUrl'):
                result.image_url = data['markImageUrl']
            elif data.get('id'):
                result.image_url = f"https://www3.wipo.int/madrid/monitor/api/brands/{data['id']}/image"

            # Designations
            designations = data.get('designations', [])
            for des in designations:
                designation = WIPODesignation(
                    country_code=des.get('countryCode', ''),
                    country_name=des.get('countryName'),
                    status=des.get('status'),
                )
                if des.get('notificationDate'):
                    designation.notification_date = self._parse_date(des['notificationDate'])
                if des.get('protectionDate'):
                    designation.protection_date = self._parse_date(des['protectionDate'])
                if des.get('refusalDate'):
                    designation.refusal_date = self._parse_date(des['refusalDate'])

                result.designations.append(designation)

        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
            result.error = f"Parse error: {e}"

        return result

    def _parse_html_response(self, number: str, html: str) -> WIPOTrademarkData:
        """Parse HTML response (fallback method)."""
        result = WIPOTrademarkData(international_number=number)

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')

            # Extract trademark name
            name_elem = soup.find('span', class_='brandName') or soup.find('div', class_='mark-feature')
            if name_elem:
                result.trademark_name = name_elem.get_text(strip=True)

            # Extract status
            status_elem = soup.find('span', class_='status') or soup.find('div', class_='status')
            if status_elem:
                result.status = self._normalize_status(status_elem.get_text(strip=True))

            # Extract dates using regex patterns
            date_patterns = {
                'expiration_date': [r'Expir\w*[:\s]+(\d{2}[./]\d{2}[./]\d{4})', r'valid until[:\s]+(\d{2}[./]\d{2}[./]\d{4})'],
                'registration_date': [r'Registration[:\s]+(\d{2}[./]\d{2}[./]\d{4})'],
                'filing_date': [r'Application[:\s]+(\d{2}[./]\d{2}[./]\d{4})'],
            }

            for field, patterns in date_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        setattr(result, field, self._parse_date(match.group(1)))
                        break

            # Extract rights holder
            holder_elem = soup.find('div', class_='holder-name') or soup.find('span', class_='holderName')
            if holder_elem:
                result.rights_holder = holder_elem.get_text(strip=True)

            # Extract ICGS classes
            classes_text = ''
            classes_elem = soup.find('div', class_='nice-classes') or soup.find('span', class_='niceClasses')
            if classes_elem:
                classes_text = classes_elem.get_text()
            else:
                # Try regex
                match = re.search(r'Class(?:es)?[:\s]+([\d,\s]+)', html, re.IGNORECASE)
                if match:
                    classes_text = match.group(1)

            if classes_text:
                result.icgs_classes = self._parse_classes(classes_text)

            # Extract image URL
            img_elem = soup.find('img', class_='brandImage') or soup.find('img', src=re.compile(r'image|brand', re.I))
            if img_elem and img_elem.get('src'):
                src = img_elem['src']
                if src.startswith('/'):
                    src = f"https://www3.wipo.int{src}"
                result.image_url = src

        except Exception as e:
            logger.error(f"Error parsing HTML response: {e}")
            result.error = f"Parse error: {e}"

        return result

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date from various formats."""
        if not date_str:
            return None

        # Clean the string
        date_str = str(date_str).strip()

        # Try various date formats
        formats = [
            '%Y-%m-%d',      # 2024-12-31 (ISO)
            '%d.%m.%Y',      # 31.12.2024
            '%d/%m/%Y',      # 31/12/2024
            '%m/%d/%Y',      # 12/31/2024 (US format)
            '%Y%m%d',        # 20241231
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        # Try to extract date with regex
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if match:
            try:
                year, month, day = map(int, match.groups())
                return date(year, month, day)
            except ValueError:
                pass

        match = re.search(r'(\d{2})[./](\d{2})[./](\d{4})', date_str)
        if match:
            try:
                day, month, year = map(int, match.groups())
                return date(year, month, day)
            except ValueError:
                pass

        logger.warning(f"Could not parse WIPO date: {date_str}")
        return None

    def _parse_classes(self, classes_str: str) -> list[int]:
        """Parse ICGS classes from string."""
        if not classes_str:
            return []

        numbers = re.findall(r'\d+', classes_str)
        classes = []

        for num in numbers:
            try:
                cls = int(num)
                if 1 <= cls <= 45:
                    classes.append(cls)
            except ValueError:
                continue

        return sorted(set(classes))

    def _normalize_status(self, status: str) -> str:
        """Normalize status string to standard values."""
        if not status:
            return ''

        status_lower = status.lower()

        if any(word in status_lower for word in ['active', 'registered', 'protected']):
            return 'registered'
        elif any(word in status_lower for word in ['expired', 'lapsed']):
            return 'expired'
        elif any(word in status_lower for word in ['pending', 'examination']):
            return 'pending'
        elif any(word in status_lower for word in ['refused', 'rejected']):
            return 'rejected'
        elif any(word in status_lower for word in ['terminated', 'cancelled']):
            return 'terminated'

        return status

    async def search_trademarks(
        self,
        query: str,
        country_code: Optional[str] = None,
        limit: int = 20
    ) -> list[WIPOTrademarkData]:
        """
        Search for trademarks in WIPO database.

        Args:
            query: Search query (trademark name or number)
            country_code: Filter by origin country code
            limit: Maximum results to return

        Returns:
            List of WIPOTrademarkData
        """
        await self._rate_limit()

        results = []

        try:
            params = {
                'query': query,
                'rows': limit,
            }
            if country_code:
                params['originCountry'] = country_code

            url = f"{self.API_URL}/brands/search"
            response = await self._client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(f"WIPO search failed: HTTP {response.status_code}")
                return results

            data = response.json()
            items = data.get('results', []) or data.get('brands', [])

            for item in items[:limit]:
                tm = WIPOTrademarkData(
                    international_number=str(item.get('id', '')),
                    trademark_name=item.get('markFeature') or item.get('wordElement'),
                    status=self._normalize_status(item.get('status', '')),
                    rights_holder=item.get('holderName'),
                )

                if item.get('expiryDate'):
                    tm.expiration_date = self._parse_date(item['expiryDate'])

                results.append(tm)

        except Exception as e:
            logger.error(f"WIPO search error: {e}")

        return results


async def test_wipo_client():
    """Test function for WIPO client."""
    # Test with known international numbers
    test_numbers = ['1234567', '7890123']

    async with WIPOClient() as client:
        for number in test_numbers:
            print(f"\nFetching WIPO trademark {number}...")
            result = await client.get_trademark_by_number(number)

            print(f"  International #: {result.international_number}")
            print(f"  Name: {result.trademark_name}")
            print(f"  Status: {result.status}")
            print(f"  Expiration: {result.expiration_date}")
            print(f"  Rights holder: {result.rights_holder}")
            print(f"  Classes: {result.icgs_classes}")
            print(f"  Image URL: {result.image_url}")
            print(f"  Designations: {len(result.designations)}")
            print(f"  Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(test_wipo_client())
