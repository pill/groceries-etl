"""Base scraper class for grocery deals."""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date, datetime
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from groceries.models.grocery import GroceryDeal, Store
from groceries.services.store_service import StoreService
from groceries.utils.json_processor import JSONProcessor


class BaseGroceryScraper(ABC):
    """Base class for grocery store scrapers."""
    
    def __init__(self, store_name: str, output_dir: Optional[str] = None):
        """
        Initialize the scraper.
        
        Args:
            store_name: Name of the store to scrape
            output_dir: Optional subdirectory within data/stage/ for output
        """
        self.store_name = store_name
        self.output_dir = output_dir
        self.json_processor = JSONProcessor()
        self.store: Optional[Store] = None
    
    async def initialize(self):
        """Initialize the scraper (get or create store record)."""
        # Get website URL if available
        website = getattr(self, 'website_url', None)
        
        self.store = await StoreService.get_or_create_store(
            name=self.store_name,
            location=None,
            website=website
        )
        
        if not self.store or not self.store.id:
            raise ValueError(f"Failed to get or create store: {self.store_name}")
        
        print(f"✅ Initialized scraper for {self.store_name} (Store ID: {self.store.id})")
    
    @abstractmethod
    async def scrape_deals(self) -> List[GroceryDeal]:
        """
        Scrape deals from the store.
        
        This method should be implemented by each store-specific scraper.
        
        Returns:
            List of GroceryDeal objects
        """
        pass
    
    async def save_deals_to_json(self, deals: List[GroceryDeal]) -> List[str]:
        """
        Save deals to JSON files.
        
        Args:
            deals: List of GroceryDeal objects to save
        
        Returns:
            List of file paths where deals were saved
        """
        saved_paths = []
        
        for deal in deals:
            try:
                # Ensure store_id is set
                if not deal.store_id and self.store:
                    deal.store_id = self.store.id
                
                path = await self.json_processor.save_deal_json(deal, self.output_dir)
                saved_paths.append(path)
                print(f"💾 Saved deal: {deal.product_name[:50]} -> {path}")
            except Exception as e:
                print(f"❌ Error saving deal {deal.product_name[:50]}: {e}")
        
        return saved_paths
    
    async def run(self) -> List[str]:
        """
        Run the scraper: scrape deals and save to JSON.
        
        Returns:
            List of file paths where deals were saved
        """
        if not self.store:
            await self.initialize()
        
        print(f"\n🔍 Scraping deals from {self.store_name}...")
        deals = await self.scrape_deals()
        
        if not deals:
            print(f"⚠️  No deals found for {self.store_name}")
            return []
        
        print(f"✅ Found {len(deals)} deals from {self.store_name}")
        
        saved_paths = await self.save_deals_to_json(deals)
        print(f"💾 Saved {len(saved_paths)} deals to JSON files")
        
        return saved_paths

