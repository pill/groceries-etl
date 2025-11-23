#!/usr/bin/env python3
"""
Script to load all JSON files from data/stage into the database.

Usage:
    python scripts/processing/load_json_to_db.py
    python scripts/processing/load_json_to_db.py --directory data/stage/hmart
    python scripts/processing/load_json_to_db.py --directory data/stage/hmart --dry-run
"""

import asyncio
import glob
import sys
from pathlib import Path
from datetime import date
from decimal import Decimal
from typing import Optional
import argparse

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from groceries.models.grocery import GroceryDeal
from groceries.services.grocery_service import GroceryService
from groceries.utils.json_processor import JSONProcessor
from groceries.database import close_pool


async def load_deal_from_json(json_file_path: str, dry_run: bool = False) -> dict:
    """
    Load a single deal JSON file into the database.
    
    Returns:
        dict with keys: success, already_exists, error, deal_id, uuid
    """
    try:
        processor = JSONProcessor()
        deal_data = await processor.load_deal_json(json_file_path)
        
        # Convert date strings to date objects
        if 'valid_from' in deal_data and isinstance(deal_data['valid_from'], str):
            deal_data['valid_from'] = date.fromisoformat(deal_data['valid_from'])
        if 'valid_to' in deal_data and isinstance(deal_data['valid_to'], str):
            deal_data['valid_to'] = date.fromisoformat(deal_data['valid_to'])
        
        # Convert Decimal strings/floats to Decimal
        for price_field in ['regular_price', 'sale_price', 'quantity', 'discount_percentage']:
            if price_field in deal_data and deal_data[price_field] is not None:
                if isinstance(deal_data[price_field], str):
                    deal_data[price_field] = Decimal(deal_data[price_field])
                elif isinstance(deal_data[price_field], float):
                    deal_data[price_field] = Decimal(str(deal_data[price_field]))
        
        deal = GroceryDeal.model_validate(deal_data)
        
        if dry_run:
            return {
                'success': True,
                'already_exists': False,
                'error': None,
                'deal_id': None,
                'uuid': deal.uuid,
                'product_name': deal.product_name
            }
        
        created_deal = await GroceryService.create(deal)
        
        if created_deal:
            return {
                'success': True,
                'already_exists': False,
                'error': None,
                'deal_id': created_deal.id,
                'uuid': created_deal.uuid,
                'product_name': created_deal.product_name
            }
        else:
            # Check if it's a duplicate by trying to fetch by UUID
            if deal.uuid:
                existing = await GroceryService.get_by_uuid(deal.uuid)
                if existing:
                    return {
                        'success': True,
                        'already_exists': True,
                        'error': None,
                        'deal_id': existing.id,
                        'uuid': deal.uuid,
                        'product_name': deal.product_name
                    }
            
            return {
                'success': False,
                'already_exists': False,
                'error': 'Failed to create deal (unknown reason)',
                'deal_id': None,
                'uuid': deal.uuid,
                'product_name': deal.product_name
            }
            
    except Exception as e:
        return {
            'success': False,
            'already_exists': False,
            'error': str(e),
            'deal_id': None,
            'uuid': None,
            'product_name': Path(json_file_path).name
        }


async def load_directory(directory: str, dry_run: bool = False, verbose: bool = False):
    """
    Load all JSON files from a directory into the database.
    
    Args:
        directory: Directory path to search for JSON files
        dry_run: If True, only validate files without loading to DB
        verbose: If True, print details for each file
    """
    # Find all JSON files
    json_files = sorted(glob.glob(f'{directory}/**/*.json', recursive=True))
    
    if not json_files:
        # Try non-recursive
        json_files = sorted(glob.glob(f'{directory}/*.json'))
    
    if not json_files:
        print(f"❌ No JSON files found in {directory}")
        return
    
    print(f"📊 Found {len(json_files)} JSON files to load")
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made to the database")
    print()
    
    successful = 0
    already_exists = 0
    failed = 0
    
    for idx, json_file in enumerate(json_files, 1):
        if verbose or idx % 10 == 0:
            print(f"[{idx}/{len(json_files)}] Processing: {Path(json_file).name}")
        
        result = await load_deal_from_json(json_file, dry_run=dry_run)
        
        if result['success']:
            if result['already_exists']:
                already_exists += 1
                if verbose:
                    print(f"  ℹ️  Already exists: {result['product_name'][:50]}")
            else:
                successful += 1
                if verbose:
                    print(f"  ✅ Loaded: {result['product_name'][:50]} (ID: {result['deal_id']})")
        else:
            failed += 1
            print(f"  ❌ Failed: {result['product_name'][:50]}")
            if result['error']:
                print(f"     Error: {result['error']}")
    
    print()
    print("=" * 60)
    print("📊 Summary:")
    print(f"  ✅ Successfully loaded: {successful}")
    print(f"  ℹ️  Already exists: {already_exists}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📁 Total files: {len(json_files)}")
    print("=" * 60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Load JSON files into the database')
    parser.add_argument(
        '--directory',
        type=str,
        default='data/stage',
        help='Directory to load JSON files from (default: data/stage)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate files without loading to database'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Show detailed output for each file'
    )
    
    args = parser.parse_args()
    
    try:
        await load_directory(args.directory, dry_run=args.dry_run, verbose=args.verbose)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_pool()


if __name__ == '__main__':
    asyncio.run(main())

