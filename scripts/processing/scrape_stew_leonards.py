#!/usr/bin/env python3
"""
Stew Leonard's scraper for shopnow.stewleonards.com

Scrapes weekly specials from Stew Leonard's Shopify-based website.
"""

import asyncio
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from bs4 import BeautifulSoup
import httpx
from playwright.async_api import async_playwright
from groceries.models.grocery import GroceryDeal, Category
from groceries.services.category_service import CategoryService
from scripts.processing.base_scraper import BaseGroceryScraper


class StewLeonardsScraper(BaseGroceryScraper):
    """
    Stew Leonard's scraper implementation.
    
    Scrapes deals from stewleonards.com including:
    - Weekly specials from store location pages
    """
    
    BASE_URL = "https://stewleonards.com"
    DEFAULT_STORE_URL = f"{BASE_URL}/stew-leonards-locations/yonkers-store/"
    
    def __init__(self, store_name: str = "Stew Leonard's", output_dir: Optional[str] = None, url: Optional[str] = None):
        """Initialize Stew Leonard's scraper.
        
        Args:
            store_name: Name of the store
            output_dir: Output directory for JSON files
            url: Optional specific store location URL to scrape (defaults to Yonkers store)
        """
        super().__init__(store_name, output_dir or "stew_leonards")
        self.website_url = self.BASE_URL
        self.specific_url = url or self.DEFAULT_STORE_URL  # Store URL, default to Yonkers
        # Use httpx for simple requests (store page)
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            },
            follow_redirects=True
        )
        self.categories_cache = {}
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    async def get_rendered_html(self, url: str) -> str:
        """Get fully rendered HTML from a JavaScript-rendered page using Playwright."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            })
            try:
                # Use 'domcontentloaded' instead of 'networkidle' for faster loading
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_timeout(8000)  # Wait longer for dynamic content to load
                
                # Try to wait for product elements to appear
                try:
                    await page.wait_for_selector('[class*="product"], [class*="item"], [data-product]', timeout=10000)
                except:
                    pass  # Continue even if selector doesn't appear
                
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')  # Scroll to trigger lazy loading
                await page.wait_for_timeout(3000)  # Wait after scrolling
                await page.evaluate('window.scrollTo(0, 0)')  # Scroll back up
                await page.wait_for_timeout(1000)
                html = await page.content()
            except Exception as e:
                print(f"⚠️  Error loading page with Playwright: {e}")
                # Try to get HTML even if there was an error
                try:
                    html = await page.content()
                except:
                    html = ""
            finally:
                await browser.close()
            return html
    
    async def get_or_create_category(self, category_name: str) -> Optional[int]:
        """Get or create a category and return its ID."""
        if category_name in self.categories_cache:
            return self.categories_cache[category_name]
        
        category = await CategoryService.get_or_create_category(category_name)
        if category and category.id:
            self.categories_cache[category_name] = category.id
            return category.id
        return None
    
    def parse_price(self, price_text: str) -> Optional[Decimal]:
        """Parse price from text like '$5.99' or '5.99' or '$799' (meaning $7.99)."""
        if not price_text:
            return None
        
        # Remove currency symbols and whitespace
        price_text = price_text.replace('$', '').replace(',', '').strip()
        
        # Extract number
        match = re.search(r'(\d+\.?\d*)', price_text)
        if match:
            try:
                price_val = Decimal(match.group(1))
                # Handle Shopify price format where $799 means $7.99 (cents format)
                # If price is > 100 and no decimal, it's likely in cents format
                if price_val >= 100 and '.' not in match.group(1):
                    price_val = price_val / 100
                return price_val
            except (ValueError, Exception):
                return None
        return None
    
    def extract_unit_and_quantity(self, product_name: str, description: str = "") -> Tuple[Optional[str], Optional[Decimal]]:
        """Extract unit and quantity from product name or description."""
        unit = None
        quantity = None
        
        # Common units
        units = ['lb', 'lbs', 'oz', 'oz.', 'g', 'kg', 'each', 'pack', 'ct', 'count', 'pcs', 'pk', 'pkg']
        
        # Look for unit patterns
        text = f"{product_name} {description}".lower()
        
        for u in units:
            pattern = rf'(\d+\.?\d*)\s*{re.escape(u)}\b'
            match = re.search(pattern, text)
            if match:
                try:
                    quantity = Decimal(match.group(1))
                    unit = u.rstrip('.')
                    break
                except (ValueError, Exception):
                    continue
        
        return unit, quantity
    
    def calculate_discount(self, regular_price: Optional[Decimal], sale_price: Optional[Decimal]) -> Optional[Decimal]:
        """Calculate discount percentage.
        
        Returns positive percentage if sale_price < regular_price (actual discount).
        Returns None if prices are invalid or sale_price >= regular_price.
        """
        if not regular_price or not sale_price or regular_price <= 0:
            return None
        
        # If sale price is higher than regular price, something is wrong - don't calculate discount
        if sale_price >= regular_price:
            return None
        
        # Calculate discount: ((regular - sale) / regular) * 100
        discount = ((regular_price - sale_price) / regular_price) * 100
        return Decimal(str(round(float(discount), 2)))
    
    async def find_weekly_specials_url(self, store_page_url: str) -> Optional[str]:
        """Find the weekly specials URL from a store location page."""
        try:
            print(f"🔍 Looking for weekly specials link on {store_page_url}...")
            
            # Use Playwright to render the store page (it may be JavaScript-rendered)
            html = await self.get_rendered_html(store_page_url)
            
            if not html:
                print("⚠️  Could not fetch store page")
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # First, check for canonical link that points to weekly specials (most reliable)
            canonical = soup.find('link', rel='canonical')
            if canonical:
                canonical_href = canonical.get('href', '')
                if 'weekly-specials' in canonical_href.lower() or 'rc-weekly-specials' in canonical_href.lower():
                    print(f"✅ Found weekly specials URL from canonical link: {canonical_href}")
                    return canonical_href
            
            # Look for links that go to shopnow.stewleonards.com with collections/weekly-specials
            # Priority: links with "collections" and "weekly-specials" or "rc-weekly-specials"
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                link_text = link.get_text(strip=True).lower()
                
                # Check if href contains the weekly specials collection pattern
                if 'shopnow.stewleonards.com' in href or href.startswith('/store/'):
                    if 'collections' in href and ('weekly-specials' in href.lower() or 'rc-weekly-specials' in href.lower()):
                        # Clean up the href
                        if href.startswith('http'):
                            full_url = href
                        elif href.startswith('/'):
                            full_url = f"https://shopnow.stewleonards.com{href}"
                        else:
                            full_url = f"https://shopnow.stewleonards.com/{href}"
                        print(f"✅ Found weekly specials URL: {full_url}")
                        return full_url
                
                # Also check link text for weekly specials
                if 'weekly' in link_text and ('special' in link_text or 'ad' in link_text):
                    if href:
                        # Make sure it's not just the storefront - must have collections/weekly-specials
                        href_lower = href.lower()
                        if 'storefront' not in href_lower and ('collections' in href_lower and ('weekly-specials' in href_lower or 'rc-weekly-specials' in href_lower)):
                            # Clean up the href
                            if href.startswith('http'):
                                full_url = href
                            elif href.startswith('/'):
                                # Check if it's a shopnow URL
                                if href.startswith('/store/'):
                                    full_url = f"https://shopnow.stewleonards.com{href}"
                                else:
                                    full_url = f"{self.BASE_URL}{href}"
                            else:
                                full_url = f"{self.BASE_URL}/{href}"
                            
                            # Remove any query parameters that might break the URL
                            if '?' in full_url:
                                full_url = full_url.split('?')[0]
                            
                            print(f"✅ Found weekly specials URL: {full_url}")
                            return full_url
            
            # Fallback: Try to find any link with "Shop All Weekly Specials" text
            shop_all_text = soup.find_all(string=re.compile(r'shop.*all.*weekly.*special', re.I))
            for text_node in shop_all_text:
                parent = text_node.find_parent('a')
                if parent:
                    href = parent.get('href', '')
                    if href:
                        # Make sure it's actually a weekly specials collection URL
                        href_lower = href.lower()
                        if 'collections' in href_lower and ('weekly-specials' in href_lower or 'rc-weekly-specials' in href_lower):
                            if href.startswith('http'):
                                full_url = href
                            elif href.startswith('/'):
                                if href.startswith('/store/'):
                                    full_url = f"https://shopnow.stewleonards.com{href}"
                                else:
                                    full_url = f"{self.BASE_URL}{href}"
                            else:
                                full_url = f"{self.BASE_URL}/{href}"
                            
                            # Remove any query parameters
                            if '?' in full_url:
                                full_url = full_url.split('?')[0]
                            
                            print(f"✅ Found weekly specials URL from text: {full_url}")
                            return full_url
            
            # Fallback: Try to construct URL from current date pattern
            # Weekly specials URLs follow pattern: rc-weekly-specials-MM-DD-MM-DD
            # Example: rc-weekly-specials-11-19-12-2 (Nov 19 - Dec 2)
            print("⚠️  Could not find weekly specials link, trying to construct from date pattern...")
            today = date.today()
            
            # Try multiple date ranges - weekly specials might start on different days
            # Try current week starting from Sunday
            days_since_sunday = today.weekday() + 1
            week_start = today - timedelta(days=days_since_sunday)
            week_end = week_start + timedelta(days=13)  # 2 weeks
            
            # Also try previous week (in case current week hasn't started yet)
            prev_week_start = week_start - timedelta(days=7)
            prev_week_end = prev_week_start + timedelta(days=13)
            
            # Try current week first
            url_suffix = f"rc-weekly-specials-{week_start.month}-{week_start.day}-{week_end.month}-{week_end.day}"
            fallback_url = f"https://shopnow.stewleonards.com/store/stew-leonards/collections/{url_suffix}"
            print(f"⚠️  Trying constructed URL: {fallback_url}")
            
            # Verify the URL works by checking if it loads
            test_html = await self.get_rendered_html(fallback_url)
            if test_html:
                test_soup = BeautifulSoup(test_html, 'html.parser')
                test_title = test_soup.find('title')
                if test_title and 'weekly special' in test_title.get_text(strip=True).lower():
                    return fallback_url
                # Try previous week if current week doesn't work
                prev_url_suffix = f"rc-weekly-specials-{prev_week_start.month}-{prev_week_start.day}-{prev_week_end.month}-{prev_week_end.day}"
                prev_fallback_url = f"https://shopnow.stewleonards.com/store/stew-leonards/collections/{prev_url_suffix}"
                print(f"⚠️  Current week URL didn't work, trying previous week: {prev_fallback_url}")
                return prev_fallback_url
            
            return fallback_url
            
        except Exception as e:
            print(f"⚠️  Error finding weekly specials URL: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def scrape_weekly_specials(self, url: Optional[str] = None) -> List[GroceryDeal]:
        """Scrape weekly specials from Stew Leonard's store page or weekly specials page."""
        deals = []
        
        try:
            # If URL is provided, use it directly
            if url:
                # Check if it's a store location page or a weekly specials page
                if '/stew-leonards-locations/' in url:
                    # It's a store location page, find the weekly specials link
                    weekly_specials_url = await self.find_weekly_specials_url(url)
                    if weekly_specials_url:
                        url = weekly_specials_url
                    else:
                        print("❌ Could not find weekly specials link from store page")
                        return deals
                # Otherwise, assume it's already a weekly specials URL (like collections/rc-weekly-specials-*)
                elif 'collections' in url and ('weekly-specials' in url.lower() or 'rc-weekly-specials' in url.lower()):
                    # It's already a weekly specials URL, use it directly
                    print(f"✅ Using provided weekly specials URL: {url}")
                # If it's neither, assume it's a weekly specials URL anyway
            else:
                # Use default Yonkers store page
                weekly_specials_url = await self.find_weekly_specials_url(self.DEFAULT_STORE_URL)
                if weekly_specials_url:
                    url = weekly_specials_url
                else:
                    print("❌ Could not determine weekly specials URL")
                    return deals
            
            print(f"📰 Scraping weekly specials from {url}...")
            
            # Use Playwright to get rendered HTML (page is JavaScript-rendered)
            html = await self.get_rendered_html(url)
            
            if not html:
                print(f"❌ Could not fetch page content from: {url}")
                return deals
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Debug: Check page title to confirm we got the right page
            page_title = soup.find('title')
            if page_title:
                print(f"📄 Page title: {page_title.get_text(strip=True)}")
            
            # Look for product items - try various selectors for different page structures
            product_items = []
            
            # Strategy 1: Look for Shopify product links (most reliable)
            product_links = soup.find_all('a', href=re.compile(r'/products/', re.I))
            if product_links:
                # Get unique parent containers for each product link
                seen_containers = set()
                for link in product_links:
                    # Find the product container (usually a parent div)
                    container = link.find_parent(['div', 'article', 'li', 'section'])
                    if container and id(container) not in seen_containers:
                        # Filter out non-product elements
                        container_text = container.get_text(strip=True).lower()
                        if 'cookie' not in container_text and 'consent' not in container_text and 'announcement' not in container_text:
                            seen_containers.add(id(container))
                            product_items.append(container)
                print(f"🔍 Found {len(product_items)} items from product links")
            
            # Strategy 2: Look for elements with data-product attribute (Shopify pattern)
            if not product_items:
                data_product_items = soup.find_all(attrs={'data-product': True})
                for item in data_product_items:
                    item_text = item.get_text(strip=True).lower()
                    if 'cookie' not in item_text and 'consent' not in item_text:
                        product_items.append(item)
                print(f"🔍 Found {len(product_items)} items with data-product attribute")
            
            # Strategy 3: Look for product cards/items with common class names
            if not product_items:
                all_candidates = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'product|item|card|deal|special', re.I))
                for item in all_candidates:
                    # Filter out cookie consent and other non-product elements
                    item_text = item.get_text(strip=True).lower()
                    item_classes = ' '.join(item.get('class', [])).lower()
                    if ('cookie' not in item_text and 'consent' not in item_text and 
                        'cookie' not in item_classes and 'consent' not in item_classes and
                        'announcement' not in item_text and 'banner' not in item_text):
                        # Also check if it has price information (likely a product)
                        if re.search(r'\$?\d+\.?\d*', item.get_text()):
                            product_items.append(item)
                print(f"🔍 Found {len(product_items)} items with product/item/card/deal/special classes (after filtering)")
            
            # Strategy 4: Look for items in a product grid
            if not product_items:
                product_grid = soup.find(['div', 'section'], class_=re.compile(r'grid|products|specials|deals', re.I))
                if product_grid:
                    grid_items = product_grid.find_all(['div', 'article', 'li'])
                    for item in grid_items:
                        item_text = item.get_text(strip=True).lower()
                        if 'cookie' not in item_text and 'consent' not in item_text and 'announcement' not in item_text:
                            product_items.append(item)
                    print(f"🔍 Found {len(product_items)} items in product grid")
            
            # Strategy 3: Look for any div/article/li that contains price information
            if not product_items:
                all_containers = soup.find_all(['div', 'article', 'li', 'section'])
                for container in all_containers:
                    text = container.get_text()
                    text_lower = text.lower()
                    # Check if it contains price-like patterns and exclude non-product elements
                    if (re.search(r'\$?\d+\.?\d*', text) and len(text) < 500 and 
                        'cookie' not in text_lower and 'consent' not in text_lower and
                        'privacy' not in text_lower and 'policy' not in text_lower):
                        product_items.append(container)
                print(f"🔍 Found {len(product_items)} items with price information (after filtering)")
            
            if not product_items:
                print("⚠️  No product items found.")
                print("💡 Saving HTML for debugging...")
                debug_file = Path("data/stage/stew_leonards_debug.html")
                debug_file.parent.mkdir(parents=True, exist_ok=True)
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"📄 Full HTML saved to: {debug_file}")
                return deals
            
            # Get current week's date range (typically weekly ads run Sun-Sat)
            today = date.today()
            # Find previous Sunday
            days_since_sunday = today.weekday() + 1
            valid_from = today - timedelta(days=days_since_sunday)
            valid_to = valid_from + timedelta(days=6)
            
            print(f"🛒 Processing {len(product_items)} potential product items...")
            
            for idx, item in enumerate(product_items, 1):
                try:
                    # Extract product name - try multiple strategies
                    name_elem = None
                    
                    # Strategy 1: Look for link with product in href (most reliable for Shopify)
                    name_elem = item.find('a', href=re.compile(r'/product|/products', re.I))
                    
                    # Strategy 2: Look for heading with title/name/product classes (but not price)
                    if not name_elem:
                        headings = item.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])
                        for heading in headings:
                            heading_classes = ' '.join(heading.get('class', [])).lower()
                            heading_text = heading.get_text(strip=True).lower()
                            # Exclude price-related headings and common non-product text
                            if ('price' not in heading_classes and 'cost' not in heading_classes and
                                'price' not in heading_text and '$' not in heading.get_text() and
                                'current price' not in heading_text and 'original price' not in heading_text and
                                'estimated' not in heading_text and 'est.' not in heading_text):
                                name_elem = heading
                                break
                    
                    # Strategy 3: Look for heading or link with title/name/product classes (exclude price)
                    if not name_elem:
                        candidates = item.find_all(['h2', 'h3', 'h4', 'h5', 'a'], class_=re.compile(r'title|name|product', re.I))
                        for candidate in candidates:
                            candidate_text = candidate.get_text(strip=True).lower()
                            candidate_classes = ' '.join(candidate.get('class', [])).lower()
                            # Exclude price-related elements and common artifacts
                            if ('price' not in candidate_classes and 'cost' not in candidate_classes and
                                'price' not in candidate_text and '$' not in candidate.get_text() and
                                'current price' not in candidate_text and 'original price' not in candidate_text and
                                'estimated' not in candidate_text and 'est.' not in candidate_text):
                                name_elem = candidate
                                break
                    
                    # Strategy 4: Look for any heading in the item (but not price-related)
                    if not name_elem:
                        headings = item.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])
                        for heading in headings:
                            heading_text = heading.get_text(strip=True).lower()
                            if ('price' not in heading_text and '$' not in heading.get_text() and
                                'current price' not in heading_text and 'original price' not in heading_text and
                                'estimated' not in heading_text):
                                name_elem = heading
                                break
                    
                    # Strategy 5: Look for span/div with product name pattern (exclude price)
                    if not name_elem:
                        candidates = item.find_all(['span', 'div'], class_=re.compile(r'name|title|heading', re.I))
                        for candidate in candidates:
                            candidate_text = candidate.get_text(strip=True).lower()
                            candidate_classes = ' '.join(candidate.get('class', [])).lower()
                            if ('price' not in candidate_classes and 'cost' not in candidate_classes and
                                'price' not in candidate_text and '$' not in candidate.get_text() and
                                'current price' not in candidate_text and 'original price' not in candidate_text and
                                'estimated' not in candidate_text):
                                name_elem = candidate
                                break
                    
                    if not name_elem:
                        if idx <= 5:  # Debug first few items
                            print(f"  ⚠️  Item {idx}: No name element found")
                            # Debug: show item HTML snippet
                            item_html = str(item)[:200] if len(str(item)) > 200 else str(item)
                            print(f"      Item HTML: {item_html}...")
                        continue
                    
                    # Try to get name from attributes first (more reliable)
                    product_name = None
                    if name_elem.name == 'a':
                        product_name = name_elem.get('title', '').strip() or name_elem.get('aria-label', '').strip()
                    
                    # If no attribute, get from text
                    if not product_name:
                        product_name = name_elem.get_text(strip=True)
                    
                    # Clean up product name - remove various prefixes and price patterns
                    if product_name:
                        # Remove various prefixes (order matters - do specific ones first)
                        # Try different patterns for /lbSave and lbSave variations
                        product_name = re.sub(r'^/lb\s*Save\s+', '', product_name, flags=re.I)  # Remove /lb Save prefix (with space)
                        product_name = re.sub(r'^/lbSave\s*', '', product_name, flags=re.I)  # Remove /lbSave prefix (no space)
                        product_name = re.sub(r'^lb\s*Save\s+', '', product_name, flags=re.I)  # Remove lb Save prefix (no leading /)
                        product_name = re.sub(r'^lbSave\s*', '', product_name, flags=re.I)  # Remove lbSave prefix (no leading /)
                        product_name = re.sub(r'^/lb\s*', '', product_name)  # Remove leading /lb
                        product_name = re.sub(r'^lb\s*', '', product_name, flags=re.I)  # Remove leading lb (case insensitive)
                        product_name = re.sub(r'^Save\s+', '', product_name, flags=re.I)  # Remove Save prefix
                        product_name = re.sub(r'^low\s+carb\s*', '', product_name, flags=re.I)  # Remove "low carb" prefix
                        product_name = re.sub(r'^\s+', '', product_name)  # Remove leading whitespace
                        # Also remove trailing "Save" if it appears
                        product_name = re.sub(r'\s+Save\s*$', '', product_name, flags=re.I)
                        # Remove any remaining leading / or -
                        product_name = re.sub(r'^[/\-]\s*', '', product_name)  # Remove leading / or -
                        
                        # Remove price patterns and common artifacts
                        product_name = re.sub(r'\$?\d+\.?\d*\s*(per\s+)?(pound|lb|oz|each|pack|ct|count|pcs|pk|pkg)\b', '', product_name, flags=re.I)
                        product_name = re.sub(r'current\s+price:?\s*\$?\d+\.?\d*', '', product_name, flags=re.I)
                        product_name = re.sub(r'original\s+price:?\s*\$?\d+\.?\d*', '', product_name, flags=re.I)
                        product_name = re.sub(r'\(estimated\)', '', product_name, flags=re.I)  # Remove (estimated)
                        product_name = re.sub(r'\(est\.\)', '', product_name, flags=re.I)  # Remove (est.)
                        product_name = re.sub(r'\$?\d+\.?\d*', '', product_name)  # Remove any remaining prices
                        product_name = re.sub(r'\s+', ' ', product_name).strip()  # Clean up whitespace
                        
                        # Skip if name looks like it's just price text or artifacts
                        if (product_name.lower().startswith('current price') or 
                            product_name.lower().startswith('original price') or
                            product_name.lower().startswith('estimated') or
                            len(product_name) < 3):
                            product_name = None
                        
                        # Final cleanup - remove any remaining prefixes that might have been missed
                        product_name = re.sub(r'^[/\-]\s*', '', product_name)  # Remove leading / or -
                        # Aggressively remove "lbSave" in any case combination at the start
                        product_name = re.sub(r'^[Ll][Bb][Ss]ave\s*', '', product_name)  # Remove lbSave (any case)
                        product_name = re.sub(r'^[Ll][Bb]\s*[Ss]ave\s*', '', product_name)  # Remove lb Save (any case)
                        product_name = re.sub(r'^[Ll][Bb]\s*', '', product_name)  # Remove any remaining lb
                        product_name = re.sub(r'^[Ss]ave\s*', '', product_name)  # Remove any remaining Save
                        product_name = product_name.strip()  # Final strip
                    
                    # Additional validation - skip if name looks invalid
                    if product_name:
                        product_name_lower = product_name.lower()
                        # Skip if it's clearly not a product name
                        if (product_name_lower.startswith('current price') or 
                            product_name_lower.startswith('original price') or
                            product_name_lower.startswith('estimated') or
                            product_name_lower.startswith('per package') or
                            product_name_lower.startswith('per pack') or
                            'current price:' in product_name_lower or
                            'original price:' in product_name_lower):
                            product_name = None
                    
                    if not product_name or len(product_name) < 3:
                        if idx <= 5:  # Debug first few items
                            print(f"  ⚠️  Item {idx}: Name element found but no valid text")
                            if name_elem:
                                print(f"      Name element text: {name_elem.get_text(strip=True)[:50]}")
                        continue
                    
                    if idx <= 3:  # Debug first few successful extractions
                        print(f"  ✅ Item {idx}: Found product name: {product_name[:50]}")
                    
                    # Extract prices - Shopify often has price elements
                    sale_price = None
                    regular_price = None
                    
                    # Find all price-related elements
                    price_elems = item.find_all(['span', 'div', 'p', 'strong'], class_=re.compile(r'price|cost|amount|money', re.I))
                    
                    # Also look for Shopify-specific price classes
                    shopify_price_elems = item.find_all(['span', 'div'], class_=re.compile(r'product.*price|compare.*price|sale.*price', re.I))
                    price_elems.extend(shopify_price_elems)
                    
                    # Look for strikethrough text (often indicates regular price)
                    strikethrough_elems = item.find_all(['span', 'div', 'del', 's'], style=re.compile(r'line-through|text-decoration.*line', re.I))
                    strikethrough_elems.extend(item.find_all(['span', 'div'], class_=re.compile(r'strike|original|was|regular|list|compare', re.I)))
                    
                    # Extract regular price from strikethrough or "was/original" elements
                    for se in strikethrough_elems:
                        price_text_se = se.get_text(strip=True)
                        price_val = self.parse_price(price_text_se)
                        if price_val and not regular_price:
                            regular_price = price_val
                    
                    # Look through all price elements
                    for pe in price_elems:
                        price_text_pe = pe.get_text(strip=True)
                        price_val = self.parse_price(price_text_pe)
                        
                        if not price_val:
                            continue
                        
                        # Check class names and parent context for price type
                        classes = ' '.join(pe.get('class', [])).lower()
                        parent_text = ''
                        if pe.parent:
                            parent_text = pe.parent.get_text(strip=True).lower()
                        
                        # Identify regular price indicators
                        is_regular = any(indicator in classes or indicator in parent_text 
                                       for indicator in ['regular', 'original', 'was', 'list', 'before', 'compare', 'strike', 'del', 'compare-at'])
                        
                        # Identify sale price indicators
                        is_sale = any(indicator in classes or indicator in parent_text 
                                    for indicator in ['sale', 'discount', 'now', 'special', 'deal', 'price', 'current'])
                        
                        if is_regular and not regular_price:
                            regular_price = price_val
                        elif is_sale and not sale_price:
                            sale_price = price_val
                        elif not is_regular and not is_sale:
                            # If ambiguous, assume higher price is regular, lower is sale
                            if not sale_price:
                                sale_price = price_val
                            elif not regular_price:
                                if price_val > sale_price:
                                    # Higher price is regular, lower is sale (already correct)
                                    regular_price = price_val
                                else:
                                    # Lower price found, swap: current sale becomes regular, new price is sale
                                    regular_price = sale_price
                                    sale_price = price_val
                    
                    # If we found a regular price but no sale price, check if there's a lower price
                    if regular_price and not sale_price:
                        # Look for any other price that might be the sale price
                        all_text = item.get_text()
                        price_matches = re.findall(r'\$?\s*(\d+\.?\d*)', all_text)
                        for match in price_matches:
                            try:
                                price_val = Decimal(match)
                                if price_val < regular_price:
                                    sale_price = price_val
                                    break
                            except (ValueError, Exception):
                                continue
                    
                    # Fallback: if only one price found, try to get it from main price element
                    if not sale_price and not regular_price:
                        price_elem = item.find(['span', 'div', 'p'], class_=re.compile(r'price|cost', re.I))
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            sale_price = self.parse_price(price_text)
                    
                    # Last resort: extract all prices from item text and use them
                    if not sale_price and not regular_price:
                        all_text = item.get_text()
                        # Find all price patterns in the text (with $ sign)
                        price_matches = re.findall(r'\$(\d+\.?\d*)', all_text)
                        prices = []
                        for match in price_matches:
                            # Use parse_price to handle cents format ($799 = $7.99)
                            parsed_price = self.parse_price(f'${match}')
                            if parsed_price:
                                prices.append(parsed_price)
                        
                        if prices:
                            # Remove duplicates and sort
                            unique_prices = sorted(set(prices), reverse=True)
                            if len(unique_prices) >= 2:
                                regular_price = unique_prices[0]
                                sale_price = unique_prices[1]
                            else:
                                sale_price = unique_prices[0]
                            
                            if idx <= 3:
                                print(f"      Extracted prices from text: {unique_prices} -> Sale: {sale_price}, Regular: {regular_price}")
                    
                    # Try to find regular price from "Original Price" or "Was" text patterns
                    if sale_price and not regular_price:
                        all_text = item.get_text()
                        # Look for patterns like "Original Price: $X.XX" or "Was $X.XX"
                        original_patterns = [
                            r'original\s+price:?\s*\$(\d+\.?\d*)',
                            r'was\s+\$(\d+\.?\d*)',
                            r'compare\s+at:?\s*\$(\d+\.?\d*)',
                            r'list\s+price:?\s*\$(\d+\.?\d*)',
                        ]
                        for pattern in original_patterns:
                            match = re.search(pattern, all_text, re.I)
                            if match:
                                parsed_price = self.parse_price(f'${match.group(1)}')
                                if parsed_price and parsed_price > sale_price:
                                    regular_price = parsed_price
                                    if idx <= 3:
                                        print(f"      Found regular price from pattern '{pattern}': {regular_price}")
                                    break
                    
                    # Validate and fix price order - sale price should be <= regular price
                    if regular_price and sale_price:
                        if sale_price > regular_price:
                            # Prices are likely swapped, swap them back
                            regular_price, sale_price = sale_price, regular_price
                        elif sale_price == regular_price:
                            # No actual discount, clear regular price
                            regular_price = None
                    
                    # Extract link (prefer product link) - do this before image extraction
                    link_elem = item.find('a', href=re.compile(r'/product', re.I))
                    if not link_elem:
                        link_elem = item.find('a', href=True)
                    source_url = None
                    if link_elem:
                        href = link_elem.get('href')
                        if href:
                            if href.startswith('http'):
                                source_url = href
                            elif href.startswith('/'):
                                # Use shopnow domain for product links
                                if '/product' in href or '/products' in href:
                                    source_url = f"https://shopnow.stewleonards.com{href}"
                                else:
                                    source_url = f"{self.BASE_URL}{href}"
                            else:
                                source_url = f"https://shopnow.stewleonards.com/{href}"
                    
                    # Extract image URL - try multiple strategies
                    image_url = None
                    img_elem = item.find('img')
                    if img_elem:
                        # Try multiple attributes in order of preference
                        for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-image']:
                            image_url = img_elem.get(attr)
                            if image_url:
                                break
                        
                        if image_url:
                            # Handle relative URLs
                            if image_url.startswith('//'):
                                image_url = f"https:{image_url}"
                            elif not image_url.startswith('http'):
                                # Check if it's a Shopify URL
                                if image_url.startswith('/'):
                                    image_url = f"https://shopnow.stewleonards.com{image_url}"
                                else:
                                    image_url = f"https://shopnow.stewleonards.com/{image_url}"
                            # Ensure it's a full URL
                            if 'cdn.shopify.com' in image_url or 'shopify' in image_url:
                                if not image_url.startswith('http'):
                                    image_url = f"https:{image_url}" if image_url.startswith('//') else f"https://{image_url}"
                    
                    # Fallback: look for image in link or parent containers
                    if not image_url and link_elem:
                        # Check if the product link has an image as a child
                        link_img = link_elem.find('img')
                        if link_img:
                            for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
                                image_url = link_img.get(attr)
                                if image_url:
                                    break
                            if image_url and not image_url.startswith('http'):
                                if image_url.startswith('//'):
                                    image_url = f"https:{image_url}"
                                elif image_url.startswith('/'):
                                    image_url = f"https://shopnow.stewleonards.com{image_url}"
                                else:
                                    image_url = f"https://shopnow.stewleonards.com/{image_url}"
                    
                    # Extract description - try multiple strategies
                    description = None
                    # Strategy 1: Look for description/summary classes
                    desc_elem = item.find(['p', 'div', 'span'], class_=re.compile(r'desc|description|summary|excerpt', re.I))
                    if desc_elem:
                        description = desc_elem.get_text(strip=True)
                    
                    # Strategy 2: Look for any paragraph that's not the product name
                    if not description:
                        paragraphs = item.find_all('p')
                        for p in paragraphs:
                            p_text = p.get_text(strip=True)
                            # Skip if it's just price or very short
                            if len(p_text) > 20 and not re.match(r'^\$?\d+', p_text):
                                description = p_text
                                break
                    
                    # Strategy 3: Look for span/div with longer text that's not the name
                    if not description:
                        text_elems = item.find_all(['span', 'div'])
                        for elem in text_elems:
                            elem_text = elem.get_text(strip=True)
                            # Skip if it's price, name, or too short
                            if elem_text and product_name and (len(elem_text) > 30 and 
                                not re.match(r'^\$?\d+', elem_text) and
                                elem_text.lower() != product_name.lower() and
                                'price' not in elem_text.lower()):
                                description = elem_text
                                break
                    
                    # Extract category (from collection/breadcrumb)
                    category_id = None
                    category_elem = item.find(['a', 'span'], class_=re.compile(r'category|tag|collection', re.I))
                    if category_elem:
                        category_name = category_elem.get_text(strip=True)
                        if category_name:
                            category_id = await self.get_or_create_category(category_name)
                    
                    # Extract unit and quantity
                    unit, quantity = self.extract_unit_and_quantity(product_name, description or "")
                    
                    # Calculate discount (only if we have both prices and sale < regular)
                    discount_percentage = self.calculate_discount(regular_price, sale_price)
                    
                    # Debug price extraction for first few items
                    if idx <= 5:
                        print(f"      Item {idx} prices - Sale: {sale_price}, Regular: {regular_price}, Price elems found: {len(price_elems)}")
                    
                    if sale_price:  # Only create deal if we have a price
                        deal = GroceryDeal(
                            store_id=self.store.id,
                            product_name=product_name,
                            category_id=category_id,
                            regular_price=regular_price,
                            sale_price=sale_price,
                            unit=unit,
                            quantity=quantity,
                            discount_percentage=discount_percentage,
                            valid_from=valid_from,
                            valid_to=valid_to,
                            source_url=source_url,
                            image_url=image_url,
                            description=description
                        )
                        deals.append(deal)
                        
                except Exception as e:
                    print(f"⚠️  Error parsing product item: {e}")
                    continue
            
            print(f"✅ Found {len(deals)} deals in weekly specials")
            
        except Exception as e:
            print(f"❌ Error scraping weekly specials: {e}")
            import traceback
            traceback.print_exc()
        
        return deals
    
    async def scrape_deals(self) -> List[GroceryDeal]:
        """
        Scrape deals from Stew Leonard's.
        
        Scrapes weekly specials from the provided URL or uses default Yonkers store page.
        """
        all_deals = []
        
        # Use specific_url if provided, otherwise use default Yonkers store page
        url_to_scrape = self.specific_url or self.DEFAULT_STORE_URL
        weekly_deals = await self.scrape_weekly_specials(url=url_to_scrape)
        all_deals.extend(weekly_deals)
        
        # Remove duplicates based on product name and store_id
        seen = set()
        unique_deals = []
        for deal in all_deals:
            key = (deal.product_name.lower().strip(), deal.store_id)
            if key not in seen:
                seen.add(key)
                unique_deals.append(deal)
        
        return unique_deals
    
    async def run(self) -> List[str]:
        """Run the scraper with proper cleanup."""
        try:
            return await super().run()
        finally:
            await self.client.aclose()


async def main():
    """Main entry point for Stew Leonard's scraper."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Scrape Stew Leonard\'s weekly specials',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default Yonkers store page
  python scripts/processing/scrape_stew_leonards.py
  
  # Use specific store location URL
  python scripts/processing/scrape_stew_leonards.py --url "https://stewleonards.com/stew-leonards-locations/yonkers-store/"
        """
    )
    parser.add_argument(
        '--url',
        type=str,
        help='Specific store location URL to scrape (e.g., https://stewleonards.com/stew-leonards-locations/yonkers-store/)'
    )
    
    args = parser.parse_args()
    
    # Create scraper with URL if provided
    scraper = StewLeonardsScraper(url=args.url)
    try:
        if args.url:
            # Scrape specific URL
            print(f"🔍 Using provided URL: {args.url}")
            await scraper.initialize()
            deals = await scraper.scrape_weekly_specials(args.url)
            saved_paths = await scraper.save_deals_to_json(deals)
        else:
            saved_paths = await scraper.run()
        
        print(f"\n✅ Scraping complete! Saved {len(saved_paths)} deals.")
        return saved_paths
    finally:
        await scraper.client.aclose()


if __name__ == '__main__':
    asyncio.run(main())

