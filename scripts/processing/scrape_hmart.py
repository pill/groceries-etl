#!/usr/bin/env python3
"""
Hmart scraper for www.hmart.com

Scrapes weekly deals, flash sales, and product listings from Hmart website.
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
from groceries.models.grocery import GroceryDeal, Category
from groceries.services.category_service import CategoryService
from scripts.processing.base_scraper import BaseGroceryScraper


class HmartScraper(BaseGroceryScraper):
    """
    Hmart scraper implementation.
    
    Scrapes deals from www.hmart.com including:
    - Weekly ads/specials
    - Flash sales
    - Best sellers
    - Category pages
    """
    
    BASE_URL = "https://www.hmart.com"
    WEEKLY_ADS_URL = f"{BASE_URL}/weekly-ads"
    FLASH_SALE_URL = f"{BASE_URL}/flash-sale"
    BEST_SELLER_URL = f"{BASE_URL}/best-seller"
    
    def __init__(self, store_name: str = "Hmart", output_dir: Optional[str] = None):
        """Initialize Hmart scraper."""
        super().__init__(store_name, output_dir or "hmart")
        self.website_url = self.BASE_URL
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
        """Parse price from text like '$5.99' or '5.99'."""
        if not price_text:
            return None
        
        # Remove currency symbols and whitespace
        price_text = price_text.replace('$', '').replace(',', '').strip()
        
        # Extract number
        match = re.search(r'(\d+\.?\d*)', price_text)
        if match:
            try:
                return Decimal(match.group(1))
            except (ValueError, Exception):
                return None
        return None
    
    def extract_unit_and_quantity(self, product_name: str, description: str = "") -> Tuple[Optional[str], Optional[Decimal]]:
        """Extract unit and quantity from product name or description."""
        unit = None
        quantity = None
        
        # Common units
        units = ['lb', 'lbs', 'oz', 'oz.', 'g', 'kg', 'each', 'pack', 'ct', 'count', 'pcs']
        
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
    
    async def scrape_weekly_ads(self) -> List[GroceryDeal]:
        """Scrape weekly ads/specials."""
        deals = []
        
        try:
            print(f"📰 Scraping weekly ads from {self.WEEKLY_ADS_URL}...")
            response = await self.client.get(self.WEEKLY_ADS_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find product items (adjust selectors based on actual HTML structure)
            # Common patterns: product-item, product-card, deal-item, etc.
            product_items = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'product|deal|item', re.I))
            
            if not product_items:
                # Try alternative selectors
                product_items = soup.find_all('div', attrs={'data-product': True})
            
            # Get current week's date range (typically weekly ads run Sun-Sat)
            today = date.today()
            # Find previous Sunday
            days_since_sunday = today.weekday() + 1
            valid_from = today - timedelta(days=days_since_sunday)
            valid_to = valid_from + timedelta(days=6)
            
            for item in product_items:
                try:
                    # Extract product name
                    name_elem = item.find(['h2', 'h3', 'h4', 'a', 'span'], class_=re.compile(r'title|name|product', re.I))
                    if not name_elem:
                        name_elem = item.find('a', href=re.compile(r'/product|/item', re.I))
                    
                    if not name_elem:
                        continue
                    
                    product_name = name_elem.get_text(strip=True)
                    if not product_name:
                        continue
                    
                    # Extract prices - look for both regular and sale prices
                    sale_price = None
                    regular_price = None
                    
                    # Find all price-related elements
                    price_elems = item.find_all(['span', 'div', 'p', 'strong'], class_=re.compile(r'price|cost|amount', re.I))
                    
                    # Also look for strikethrough text (often indicates regular price)
                    strikethrough_elems = item.find_all(['span', 'div', 'del', 's'], style=re.compile(r'line-through|text-decoration.*line', re.I))
                    strikethrough_elems.extend(item.find_all(['span', 'div'], class_=re.compile(r'strike|original|was|regular|list', re.I)))
                    
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
                                       for indicator in ['regular', 'original', 'was', 'list', 'before', 'compare', 'strike', 'del'])
                        
                        # Identify sale price indicators
                        is_sale = any(indicator in classes or indicator in parent_text 
                                    for indicator in ['sale', 'discount', 'now', 'special', 'deal', 'price'])
                        
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
                    
                    # Extract image URL
                    img_elem = item.find('img')
                    image_url = None
                    if img_elem:
                        image_url = img_elem.get('src') or img_elem.get('data-src')
                        if image_url and not image_url.startswith('http'):
                            image_url = f"{self.BASE_URL}{image_url}"
                    
                    # Extract link
                    link_elem = item.find('a', href=True)
                    source_url = None
                    if link_elem:
                        href = link_elem.get('href')
                        if href:
                            if href.startswith('http'):
                                source_url = href
                            else:
                                source_url = f"{self.BASE_URL}{href}"
                    
                    # Extract description
                    desc_elem = item.find(['p', 'div', 'span'], class_=re.compile(r'desc|description', re.I))
                    description = desc_elem.get_text(strip=True) if desc_elem else None
                    
                    # Extract category
                    category_id = None
                    category_elem = item.find(['a', 'span'], class_=re.compile(r'category|tag', re.I))
                    if category_elem:
                        category_name = category_elem.get_text(strip=True)
                        if category_name:
                            category_id = await self.get_or_create_category(category_name)
                    
                    # Extract unit and quantity
                    unit, quantity = self.extract_unit_and_quantity(product_name, description or "")
                    
                    # Validate and fix price order - sale price should be <= regular price
                    if regular_price and sale_price:
                        if sale_price > regular_price:
                            # Prices are likely swapped, swap them back
                            regular_price, sale_price = sale_price, regular_price
                        elif sale_price == regular_price:
                            # No actual discount, clear regular price
                            regular_price = None
                    
                    # Calculate discount (only if we have both prices and sale < regular)
                    discount_percentage = self.calculate_discount(regular_price, sale_price)
                    
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
            
            print(f"✅ Found {len(deals)} deals in weekly ads")
            
        except Exception as e:
            print(f"❌ Error scraping weekly ads: {e}")
            import traceback
            traceback.print_exc()
        
        return deals
    
    async def scrape_flash_sale(self) -> List[GroceryDeal]:
        """Scrape flash sale items."""
        deals = []
        
        try:
            print(f"⚡ Scraping flash sale from {self.FLASH_SALE_URL}...")
            response = await self.client.get(self.FLASH_SALE_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Flash sales typically have limited time (e.g., 24-48 hours)
            today = date.today()
            valid_from = today
            valid_to = today + timedelta(days=1)  # Assume 24-hour flash sale
            
            # Similar parsing logic as weekly ads
            product_items = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'product|deal|item|flash', re.I))
            
            for item in product_items:
                try:
                    # Similar extraction logic as weekly_ads
                    name_elem = item.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name', re.I))
                    if not name_elem:
                        continue
                    
                    product_name = name_elem.get_text(strip=True)
                    if not product_name:
                        continue
                    
                    # Extract prices - use same logic as weekly ads
                    sale_price = None
                    regular_price = None
                    
                    # Find all price-related elements
                    price_elems = item.find_all(['span', 'div', 'p', 'strong'], class_=re.compile(r'price|cost|amount', re.I))
                    
                    # Look for strikethrough text (often indicates regular price)
                    strikethrough_elems = item.find_all(['span', 'div', 'del', 's'], style=re.compile(r'line-through|text-decoration.*line', re.I))
                    strikethrough_elems.extend(item.find_all(['span', 'div'], class_=re.compile(r'strike|original|was|regular|list', re.I)))
                    
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
                                       for indicator in ['regular', 'original', 'was', 'list', 'before', 'compare', 'strike', 'del'])
                        
                        # Identify sale price indicators
                        is_sale = any(indicator in classes or indicator in parent_text 
                                    for indicator in ['sale', 'discount', 'now', 'special', 'deal', 'price'])
                        
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
                    
                    if not sale_price:
                        continue
                    
                    # Extract other details
                    img_elem = item.find('img')
                    image_url = None
                    if img_elem:
                        image_url = img_elem.get('src') or img_elem.get('data-src')
                        if image_url and not image_url.startswith('http'):
                            image_url = f"{self.BASE_URL}{image_url}"
                    
                    link_elem = item.find('a', href=True)
                    source_url = None
                    if link_elem:
                        href = link_elem.get('href')
                        if href:
                            source_url = f"{self.BASE_URL}{href}" if not href.startswith('http') else href
                    
                    unit, quantity = self.extract_unit_and_quantity(product_name)
                    
                    # Validate and fix price order - sale price should be <= regular price
                    if regular_price and sale_price:
                        if sale_price > regular_price:
                            # Prices are likely swapped, swap them back
                            regular_price, sale_price = sale_price, regular_price
                        elif sale_price == regular_price:
                            # No actual discount, clear regular price
                            regular_price = None
                    
                    # Calculate discount (only if we have both prices and sale < regular)
                    discount_percentage = self.calculate_discount(regular_price, sale_price)
                    
                    deal = GroceryDeal(
                        store_id=self.store.id,
                        product_name=product_name,
                        regular_price=regular_price,
                        sale_price=sale_price,
                        unit=unit,
                        quantity=quantity,
                        discount_percentage=discount_percentage,
                        valid_from=valid_from,
                        valid_to=valid_to,
                        source_url=source_url,
                        image_url=image_url,
                        description="Flash Sale Item"
                    )
                    deals.append(deal)
                    
                except Exception as e:
                    print(f"⚠️  Error parsing flash sale item: {e}")
                    continue
            
            print(f"✅ Found {len(deals)} flash sale deals")
            
        except Exception as e:
            print(f"❌ Error scraping flash sale: {e}")
        
        return deals
    
    async def scrape_deals(self) -> List[GroceryDeal]:
        """
        Scrape deals from Hmart.
        
        Combines deals from weekly ads and flash sales.
        """
        all_deals = []
        
        # Scrape weekly ads
        weekly_deals = await self.scrape_weekly_ads()
        all_deals.extend(weekly_deals)
        
        # Scrape flash sales
        flash_deals = await self.scrape_flash_sale()
        all_deals.extend(flash_deals)
        
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
    """Main entry point for Hmart scraper."""
    scraper = HmartScraper()
    try:
        saved_paths = await scraper.run()
        print(f"\n✅ Scraping complete! Saved {len(saved_paths)} deals.")
        return saved_paths
    finally:
        await scraper.client.aclose()


if __name__ == '__main__':
    asyncio.run(main())

