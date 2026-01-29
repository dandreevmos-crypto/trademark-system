"""FIPS (Rospatent) trademark scraper using Playwright.

FIPS URL pattern:
https://www1.fips.ru/registers-doc-view/fips_servlet?DB=RUTM&DocNumber={number}

The site uses JavaScript rendering, so we need Playwright.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from urllib.parse import quote

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class FIPSTrademarkData:
    """Data extracted from FIPS for a trademark."""

    registration_number: str
    application_number: Optional[str] = None
    trademark_name: Optional[str] = None
    status: Optional[str] = None
    filing_date: Optional[date] = None
    registration_date: Optional[date] = None
    expiration_date: Optional[date] = None
    rights_holder: Optional[str] = None
    icgs_classes: Optional[list[int]] = None
    goods_services: Optional[dict[int, str]] = None  # class -> description
    image_url: Optional[str] = None
    raw_html: Optional[str] = None
    error: Optional[str] = None


class FIPSScraper:
    """Scraper for FIPS (fips.ru) trademark database.

    Uses Playwright for JavaScript-rendered pages.
    Implements rate limiting to avoid overloading the server.
    """

    BASE_URL = "https://www1.fips.ru/registers-doc-view/fips_servlet"
    SEARCH_URL = "https://www1.fips.ru/registers-web-tm"

    # Rate limiting: requests per minute from settings
    RATE_LIMIT = getattr(settings, 'fips_rate_limit_per_minute', 12)
    MIN_DELAY = 60.0 / RATE_LIMIT  # Minimum seconds between requests

    def __init__(self):
        self._last_request_time: float = 0
        self._browser = None
        self._context = None
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._start_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_browser()

    async def _start_browser(self):
        """Start Playwright browser."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        self._context = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ru-RU'
        )
        logger.info("FIPS scraper browser started")

    async def _close_browser(self):
        """Close Playwright browser."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("FIPS scraper browser closed")

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self.MIN_DELAY:
                wait_time = self.MIN_DELAY - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            self._last_request_time = asyncio.get_event_loop().time()

    async def get_trademark_by_number(
        self,
        registration_number: str,
        retries: int = 3
    ) -> FIPSTrademarkData:
        """
        Fetch trademark data from FIPS by registration number.

        Args:
            registration_number: Russian trademark registration number
            retries: Number of retry attempts on failure

        Returns:
            FIPSTrademarkData with extracted information
        """
        result = FIPSTrademarkData(registration_number=registration_number)

        for attempt in range(retries):
            try:
                await self._rate_limit()

                # Build URL
                url = f"{self.BASE_URL}?DB=RUTM&DocNumber={quote(registration_number)}"
                logger.info(f"Fetching FIPS data for {registration_number} (attempt {attempt + 1})")

                # Create new page
                page = await self._context.new_page()

                try:
                    # Navigate to page
                    response = await page.goto(url, wait_until='networkidle', timeout=30000)

                    if response.status != 200:
                        result.error = f"HTTP {response.status}"
                        continue

                    # Wait for content to load
                    await page.wait_for_selector('body', timeout=10000)

                    # Check if trademark exists
                    content = await page.content()
                    if 'не найден' in content.lower() or 'not found' in content.lower():
                        result.error = "Trademark not found"
                        return result

                    # Extract data
                    result = await self._extract_data(page, registration_number)
                    result.raw_html = content

                    return result

                finally:
                    await page.close()

            except PlaywrightTimeout as e:
                logger.warning(f"Timeout for {registration_number}: {e}")
                result.error = f"Timeout: {e}"
                if attempt < retries - 1:
                    await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error fetching {registration_number}: {e}")
                result.error = str(e)
                if attempt < retries - 1:
                    await asyncio.sleep(5)

        return result

    async def _extract_data(self, page: Page, registration_number: str) -> FIPSTrademarkData:
        """Extract trademark data from loaded page."""
        result = FIPSTrademarkData(registration_number=registration_number)

        try:
            # Try to extract registration number (confirmation)
            reg_num = await self._extract_field(page, [
                '//td[contains(text(), "(210)")]/following-sibling::td',
                '//td[contains(text(), "Номер заявки")]/following-sibling::td',
            ])
            if reg_num:
                result.application_number = reg_num.strip()

            # Extract trademark name/description
            name = await self._extract_field(page, [
                '//td[contains(text(), "(540)")]/following-sibling::td',
                '//td[contains(text(), "словесный элемент")]/following-sibling::td',
            ])
            if name:
                result.trademark_name = name.strip()

            # Extract status
            status = await self._extract_field(page, [
                '//td[contains(text(), "Статус")]/following-sibling::td',
                '//span[contains(@class, "status")]',
            ])
            if status:
                result.status = self._normalize_status(status.strip())

            # Extract filing date (date of application)
            filing = await self._extract_field(page, [
                '//td[contains(text(), "(220)")]/following-sibling::td',
                '//td[contains(text(), "Дата подачи")]/following-sibling::td',
            ])
            if filing:
                result.filing_date = self._parse_date(filing)

            # Extract registration date
            reg_date = await self._extract_field(page, [
                '//td[contains(text(), "(151)")]/following-sibling::td',
                '//td[contains(text(), "Дата регистрации")]/following-sibling::td',
            ])
            if reg_date:
                result.registration_date = self._parse_date(reg_date)

            # Extract expiration date
            exp_date = await self._extract_field(page, [
                '//td[contains(text(), "(181)")]/following-sibling::td',
                '//td[contains(text(), "Срок действия")]/following-sibling::td',
                '//td[contains(text(), "истечения срока")]/following-sibling::td',
            ])
            if exp_date:
                result.expiration_date = self._parse_date(exp_date)

            # Extract rights holder
            holder = await self._extract_field(page, [
                '//td[contains(text(), "(732)")]/following-sibling::td',
                '//td[contains(text(), "Правообладатель")]/following-sibling::td',
            ])
            if holder:
                result.rights_holder = holder.strip()

            # Extract ICGS classes and goods/services descriptions
            classes_text = await self._extract_field(page, [
                '//td[contains(text(), "(511)")]/following-sibling::td',
                '//td[contains(text(), "МКТУ")]/following-sibling::td',
            ])
            if classes_text:
                result.icgs_classes = self._parse_classes(classes_text)
                result.goods_services = self._parse_goods_services(classes_text)

            # Extract image URL
            image_url = await self._extract_image_url(page)
            if image_url:
                result.image_url = image_url

        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            result.error = f"Extraction error: {e}"

        return result

    async def _extract_field(self, page: Page, xpaths: list[str]) -> Optional[str]:
        """Try multiple XPath selectors to extract a field."""
        for xpath in xpaths:
            try:
                element = await page.query_selector(f'xpath={xpath}')
                if element:
                    text = await element.inner_text()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        return None

    async def _extract_image_url(self, page: Page) -> Optional[str]:
        """Extract trademark image URL from page."""
        try:
            # Try to find image in various locations
            selectors = [
                'img[src*="getImage"]',
                'img[src*="trademark"]',
                'img.tm-image',
                '//img[contains(@src, "fips")]',
            ]

            for selector in selectors:
                try:
                    if selector.startswith('//'):
                        element = await page.query_selector(f'xpath={selector}')
                    else:
                        element = await page.query_selector(selector)

                    if element:
                        src = await element.get_attribute('src')
                        if src:
                            # Make absolute URL if relative
                            if src.startswith('/'):
                                src = f"https://www1.fips.ru{src}"
                            return src
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Could not extract image URL: {e}")

        return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date from various formats."""
        if not date_str:
            return None

        # Clean the string
        date_str = date_str.strip()

        # Try various date formats
        formats = [
            '%d.%m.%Y',      # 31.12.2024
            '%Y-%m-%d',      # 2024-12-31
            '%d/%m/%Y',      # 31/12/2024
            '%d %B %Y',      # 31 December 2024
            '%d %b %Y',      # 31 Dec 2024
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        # Try to extract date with regex
        match = re.search(r'(\d{2})[./](\d{2})[./](\d{4})', date_str)
        if match:
            try:
                day, month, year = map(int, match.groups())
                return date(year, month, day)
            except ValueError:
                pass

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def _parse_classes(self, classes_str: str) -> list[int]:
        """Parse ICGS classes from string."""
        if not classes_str:
            return []

        # Find all numbers in the string
        numbers = re.findall(r'\d+', classes_str)
        classes = []

        for num in numbers:
            try:
                cls = int(num)
                if 1 <= cls <= 45:  # Valid ICGS classes
                    classes.append(cls)
            except ValueError:
                continue

        return sorted(set(classes))

    def _parse_goods_services(self, text: str) -> dict[int, str]:
        """Parse goods/services descriptions by class from FIPS format.

        FIPS format example:
        "03 - мыла; парфюмерные изделия; косметика
         25 - одежда, обувь, головные уборы
         35 - реклама; менеджмент в сфере бизнеса"
        """
        result = {}
        if not text:
            return result

        # Split by class numbers (pattern: "NN - " or "NN:")
        # First, normalize the text
        text = text.replace('\n', ' ').replace('\r', ' ')

        # Find all class entries
        # Pattern: class number followed by dash/colon and description
        pattern = r'(\d{1,2})\s*[-:–—]\s*([^0-9]+?)(?=\d{1,2}\s*[-:–—]|$)'
        matches = re.findall(pattern, text, re.IGNORECASE)

        for match in matches:
            try:
                class_num = int(match[0])
                description = match[1].strip().rstrip(',;.')
                if 1 <= class_num <= 45 and description:
                    result[class_num] = description
            except (ValueError, IndexError):
                continue

        return result

    def _normalize_status(self, status: str) -> str:
        """Normalize status string to standard values."""
        status_lower = status.lower()

        if any(word in status_lower for word in ['действует', 'зарегистрирован', 'active']):
            return 'registered'
        elif any(word in status_lower for word in ['прекращ', 'аннулир', 'terminated']):
            return 'terminated'
        elif any(word in status_lower for word in ['истек', 'expired']):
            return 'expired'
        elif any(word in status_lower for word in ['делопроизводств', 'pending']):
            return 'pending'
        elif any(word in status_lower for word in ['отказ', 'rejected']):
            return 'rejected'

        return status


async def test_fips_scraper():
    """Test function for FIPS scraper."""
    # Test with a known trademark number
    test_numbers = ['123456', '789012']

    async with FIPSScraper() as scraper:
        for number in test_numbers:
            print(f"\nFetching trademark {number}...")
            result = await scraper.get_trademark_by_number(number)

            print(f"  Registration: {result.registration_number}")
            print(f"  Name: {result.trademark_name}")
            print(f"  Status: {result.status}")
            print(f"  Expiration: {result.expiration_date}")
            print(f"  Rights holder: {result.rights_holder}")
            print(f"  Classes: {result.icgs_classes}")
            print(f"  Image URL: {result.image_url}")
            print(f"  Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(test_fips_scraper())
