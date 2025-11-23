"""Command-line interface commands."""

import asyncio
import click
import json
from typing import Optional
from pathlib import Path
from datetime import date
from decimal import Decimal

from ..database import test_connection, close_pool, get_pool
from ..services.grocery_service import GroceryService
from ..services.store_service import StoreService
from ..services.category_service import CategoryService
from ..models.grocery import GroceryDeal
from ..utils.json_processor import JSONProcessor


@click.group()
def main():
    """Grocery ETL CLI - Weekly grocery deals data pipeline."""
    pass


@main.command()
def test_db():
    """Test database connection."""
    asyncio.run(_test_db())


async def _test_db():
    """Test database connection."""
    try:
        success = await test_connection()
        if success:
            click.echo("✅ Database connection successful!")
        else:
            click.echo("❌ Database connection failed!")
            exit(1)
    finally:
        await close_pool()


@main.command()
@click.argument('json_file_path')
def load_deal(json_file_path: str):
    """Load a grocery deal JSON file into the database."""
    asyncio.run(_load_deal(json_file_path))


async def _load_deal(json_file_path: str):
    """Load a grocery deal JSON file into the database."""
    try:
        click.echo(f"💾 Loading deal from {json_file_path}...")
        
        processor = JSONProcessor()
        deal_data = await processor.load_deal_json(json_file_path)
        
        # Convert date strings to date objects
        if 'valid_from' in deal_data and isinstance(deal_data['valid_from'], str):
            deal_data['valid_from'] = date.fromisoformat(deal_data['valid_from'])
        if 'valid_to' in deal_data and isinstance(deal_data['valid_to'], str):
            deal_data['valid_to'] = date.fromisoformat(deal_data['valid_to'])
        
        # Convert Decimal strings to Decimal
        for price_field in ['regular_price', 'sale_price', 'quantity', 'discount_percentage']:
            if price_field in deal_data and deal_data[price_field] is not None:
                if isinstance(deal_data[price_field], str):
                    deal_data[price_field] = Decimal(deal_data[price_field])
                elif isinstance(deal_data[price_field], float):
                    deal_data[price_field] = Decimal(str(deal_data[price_field]))
        
        deal = GroceryDeal.model_validate(deal_data)
        
        created_deal = await GroceryService.create(deal)
        
        if created_deal:
            click.echo(f"✅ Successfully loaded deal: {created_deal.product_name}")
            click.echo(f"🆔 Deal ID: {created_deal.id}")
            click.echo(f"🔑 UUID: {created_deal.uuid}")
        else:
            click.echo(f"❌ Failed to load deal (may be duplicate)")
            exit(1)
    except Exception as e:
        click.echo(f"❌ Error loading deal: {str(e)}")
        import traceback
        click.echo(traceback.format_exc())
        exit(1)
    finally:
        await close_pool()


@main.command()
@click.option('--limit', default=10, help='Number of deals to show')
@click.option('--store', type=str, help='Filter by store name')
def list_deals(limit: int, store: Optional[str]):
    """List recent deals from the database."""
    asyncio.run(_list_deals(limit, store))


async def _list_deals(limit: int, store: Optional[str]):
    """List recent deals."""
    try:
        from ..models.grocery import GroceryDealFilters
        
        filters = None
        if store:
            store_obj = await StoreService.get_by_id(int(store)) if store.isdigit() else None
            if not store_obj:
                # Try to find by name
                # For now, just use store_id if it's a number
                if store.isdigit():
                    filters = GroceryDealFilters(store_id=int(store))
                else:
                    click.echo(f"⚠️  Store '{store}' not found. Showing all deals.")
        
        click.echo(f"📋 Fetching {limit} recent deals...")
        deals = await GroceryService.get_all(filters=filters, limit=limit)
        
        if not deals:
            click.echo("📭 No deals found in database")
            return
        
        for i, deal in enumerate(deals, 1):
            click.echo(f"{i}. {deal.product_name}")
            if deal.store:
                click.echo(f"   🏪 Store: {deal.store.name}")
            if deal.sale_price:
                click.echo(f"   💰 Sale Price: ${deal.sale_price}")
                if deal.regular_price:
                    click.echo(f"   💵 Regular Price: ${deal.regular_price}")
            if deal.discount_percentage:
                click.echo(f"   🎯 Discount: {deal.discount_percentage}%")
            click.echo(f"   📅 Valid: {deal.valid_from} to {deal.valid_to}")
            click.echo()
    except Exception as e:
        click.echo(f"❌ Error listing deals: {str(e)}")
        import traceback
        click.echo(traceback.format_exc())
        exit(1)
    finally:
        await close_pool()


@main.command('search')
@click.argument('search_term')
@click.option('--limit', default=10, help='Number of results to show')
def search_deals(search_term: str, limit: int):
    """Search deals by product name."""
    asyncio.run(_search_deals(search_term, limit))


async def _search_deals(search_term: str, limit: int):
    """Search deals."""
    try:
        click.echo(f"🔍 Searching for '{search_term}'...")
        deals = await GroceryService.search(search_term, limit=limit)
        
        if not deals:
            click.echo("📭 No deals found")
            return
        
        click.echo(f"✅ Found {len(deals)} deals:")
        for i, deal in enumerate(deals, 1):
            click.echo(f"{i}. {deal.product_name}")
            if deal.store:
                click.echo(f"   🏪 Store: {deal.store.name}")
            if deal.sale_price:
                click.echo(f"   💰 Sale Price: ${deal.sale_price}")
            click.echo()
    except Exception as e:
        click.echo(f"❌ Error searching deals: {str(e)}")
        exit(1)
    finally:
        await close_pool()


@main.command()
def stats():
    """Show database statistics."""
    asyncio.run(_stats())


async def _stats():
    """Show statistics."""
    try:
        stats = await GroceryService.get_stats()
        
        click.echo("📊 Database Statistics:")
        click.echo(f"   Total Deals: {stats.get('total_deals', 0)}")
        click.echo(f"   Unique Stores: {stats.get('unique_stores', 0)}")
        click.echo(f"   Unique Categories: {stats.get('unique_categories', 0)}")
        if stats.get('avg_discount'):
            click.echo(f"   Average Discount: {stats.get('avg_discount', 0):.2f}%")
        if stats.get('avg_sale_price'):
            click.echo(f"   Average Sale Price: ${stats.get('avg_sale_price', 0):.2f}")
        if stats.get('earliest_deal'):
            click.echo(f"   Earliest Deal: {stats.get('earliest_deal')}")
        if stats.get('latest_deal'):
            click.echo(f"   Latest Deal: {stats.get('latest_deal')}")
    except Exception as e:
        click.echo(f"❌ Error getting statistics: {str(e)}")
        exit(1)
    finally:
        await close_pool()


@main.command('load-directory')
@click.argument('directory', type=str, required=False, default='data/stage')
@click.option('--dry-run', is_flag=True, help='Validate files without loading to database')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output for each file')
def load_directory(directory: str, dry_run: bool, verbose: bool):
    """Load all JSON files from a directory into the database."""
    asyncio.run(_load_directory(directory, dry_run, verbose))


async def _load_directory(directory: str, dry_run: bool, verbose: bool):
    """Load directory of JSON files."""
    import sys
    from pathlib import Path
    
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'processing'))
    
    try:
        from scripts.processing.load_json_to_db import load_directory
        await load_directory(directory, dry_run=dry_run, verbose=verbose)
    except Exception as e:
        click.echo(f"❌ Error loading directory: {str(e)}")
        import traceback
        click.echo(traceback.format_exc())
        exit(1)
    finally:
        await close_pool()


@main.command('scrape')
@click.option('--store', type=str, help='Store name to scrape')
@click.option('--url', type=str, help='Specific URL to scrape (for stores that support it)')
@click.option('--all', is_flag=True, help='Scrape all stores')
def scrape(store: Optional[str], url: Optional[str], all: bool):
    """Scrape deals from stores."""
    asyncio.run(_scrape(store, url, all))


async def _scrape(store: Optional[str], url: Optional[str], all: bool):
    """Scrape deals."""
    import sys
    from pathlib import Path
    
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    scripts_path = PROJECT_ROOT / 'scripts' / 'processing'
    sys.path.insert(0, str(PROJECT_ROOT))
    
    try:
        if all:
            click.echo("🔍 Scraping all stores...")
            # Import and run the scraper
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "scrape_grocery_deals",
                scripts_path / "scrape_grocery_deals.py"
            )
            scraper_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(scraper_module)
            await scraper_module.main()
        elif store:
            click.echo(f"🔍 Scraping {store}...")
            if url:
                click.echo(f"📍 Using URL: {url}")
            
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "scrape_grocery_deals",
                scripts_path / "scrape_grocery_deals.py"
            )
            scraper_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(scraper_module)
            
            # Use appropriate scraper based on store name
            scraper_class = scraper_module.ExampleScraper
            store_lower = store.lower()
            
            if store_lower in ['hmart', 'h-mart']:
                # Import Hmart scraper
                hmart_spec = importlib.util.spec_from_file_location(
                    "scrape_hmart",
                    scripts_path / "scrape_hmart.py"
                )
                hmart_module = importlib.util.module_from_spec(hmart_spec)
                hmart_spec.loader.exec_module(hmart_module)
                scraper_class = hmart_module.HmartScraper
            elif store_lower in ['stew leonards', 'stew leonard\'s', 'stew leonard', 'stew-leonards', 'stew-leonard\'s', 'stew-leonard']:
                # Import Stew Leonard's scraper
                stew_spec = importlib.util.spec_from_file_location(
                    "scrape_stew_leonards",
                    scripts_path / "scrape_stew_leonards.py"
                )
                stew_module = importlib.util.module_from_spec(stew_spec)
                stew_spec.loader.exec_module(stew_module)
                scraper_class = stew_module.StewLeonardsScraper
                
                # If URL is provided, create scraper with URL and run directly
                if url:
                    scraper = scraper_class(url=url)
                    await scraper.initialize()
                    deals = await scraper.scrape_weekly_specials(url=url)
                    saved_paths = await scraper.save_deals_to_json(deals)
                    click.echo(f"✅ Scraping complete! Saved {len(saved_paths)} deals.")
                    return
            
            await scraper_module.scrape_store(store, scraper_class)
        else:
            click.echo("❌ Please specify --store or --all")
            exit(1)
    except Exception as e:
        click.echo(f"❌ Error scraping: {str(e)}")
        import traceback
        click.echo(traceback.format_exc())
        exit(1)


@main.command('init-stores')
def init_stores():
    """Initialize stores in the database."""
    asyncio.run(_init_stores())


async def _init_stores():
    """Initialize stores."""
    try:
        click.echo("🏪 Initializing stores...")
        
        # Define stores to initialize
        stores_to_init = [
            {"name": "Hmart", "website": "https://www.hmart.com"},
            {"name": "Stew Leonard's", "website": "https://stewleonards.com"},
        ]
        
        initialized_count = 0
        for store_info in stores_to_init:
            store = await StoreService.get_or_create_store(
                name=store_info["name"],
                location=None,
                website=store_info["website"]
            )
            
            if store:
                click.echo(f"✅ {store_info['name']} (ID: {store.id})")
                initialized_count += 1
            else:
                click.echo(f"❌ Failed to initialize {store_info['name']}")
        
        click.echo(f"\n✅ Successfully initialized {initialized_count} store(s)")
    except Exception as e:
        click.echo(f"❌ Error initializing stores: {str(e)}")
        import traceback
        click.echo(traceback.format_exc())
        exit(1)
    finally:
        await close_pool()


@main.command('update-store')
@click.option('--id', type=int, help='Store ID to update')
@click.option('--name', type=str, help='Store name to find (if --id not provided)')
@click.option('--new-name', type=str, help='New store name')
@click.option('--location', type=str, help='New location')
@click.option('--website', type=str, help='New website URL')
def update_store(id: Optional[int], name: Optional[str], new_name: Optional[str], location: Optional[str], website: Optional[str]):
    """Update store information."""
    asyncio.run(_update_store(id, name, new_name, location, website))


async def _update_store(store_id: Optional[int], store_name: Optional[str], new_name: Optional[str], location: Optional[str], website: Optional[str]):
    """Update store information."""
    try:
        # Find the store
        store = None
        if store_id:
            store = await StoreService.get_by_id(store_id)
            if not store:
                click.echo(f"❌ Store with ID {store_id} not found")
                exit(1)
        elif store_name:
            # Find by name
            pool = await get_pool()
            async with pool.acquire() as conn:
                query = "SELECT * FROM stores WHERE name = $1"
                row = await conn.fetchrow(query, store_name)
                if row:
                    from ..models.grocery import Store
                    store = Store(
                        id=row['id'],
                        name=row['name'],
                        location=row['location'],
                        website=row['website'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
            if not store:
                click.echo(f"❌ Store '{store_name}' not found")
                exit(1)
        else:
            click.echo("❌ Please provide either --id or --name to identify the store")
            exit(1)
        
        click.echo(f"📝 Updating store: {store.name} (ID: {store.id})")
        
        # Update the store
        updated_store = await StoreService.update_store(
            store_id=store.id,
            name=new_name,
            location=location,
            website=website
        )
        
        if updated_store:
            click.echo(f"✅ Store updated successfully:")
            click.echo(f"   ID: {updated_store.id}")
            click.echo(f"   Name: {updated_store.name}")
            if updated_store.location:
                click.echo(f"   Location: {updated_store.location}")
            if updated_store.website:
                click.echo(f"   Website: {updated_store.website}")
        else:
            click.echo("❌ Failed to update store")
            exit(1)
    except Exception as e:
        click.echo(f"❌ Error updating store: {str(e)}")
        import traceback
        click.echo(traceback.format_exc())
        exit(1)
    finally:
        await close_pool()

