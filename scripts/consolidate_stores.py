#!/usr/bin/env python3
"""Script to consolidate duplicate store entries."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from groceries.database.connection import get_pool, close_pool


async def consolidate_stores(keep_store_id: int, delete_store_id: int, dry_run: bool = True):
    """Consolidate two stores by moving deals from one to another and deleting the duplicate."""
    pool = await get_pool()
    
    try:
        async with pool.acquire() as conn:
            # Start a transaction
            async with conn.transaction():
                # Get store info
                keep_store = await conn.fetchrow('SELECT * FROM stores WHERE id = $1', keep_store_id)
                delete_store = await conn.fetchrow('SELECT * FROM stores WHERE id = $1', delete_store_id)
                
                if not keep_store:
                    print(f"❌ Store with ID {keep_store_id} not found")
                    return False
                
                if not delete_store:
                    print(f"❌ Store with ID {delete_store_id} not found")
                    return False
                
                print(f"📋 Consolidation Plan:")
                print(f"   Keep: ID {keep_store_id} - '{keep_store['name']}'")
                print(f"   Delete: ID {delete_store_id} - '{delete_store['name']}'")
                
                # Count deals in each store
                keep_deals_count = await conn.fetchval(
                    'SELECT COUNT(*) FROM grocery_deals WHERE store_id = $1', keep_store_id
                )
                delete_deals_count = await conn.fetchval(
                    'SELECT COUNT(*) FROM grocery_deals WHERE store_id = $1', delete_store_id
                )
                
                print(f"   Deals in keep store: {keep_deals_count}")
                print(f"   Deals in delete store: {delete_deals_count}")
                
                if dry_run:
                    print("\n🔍 DRY RUN - No changes will be made")
                    print("   Would update deals: ", delete_deals_count > 0)
                    print("   Would delete store: ", delete_store_id)
                    return True
                
                # Update all deals from delete_store to keep_store
                if delete_deals_count > 0:
                    updated = await conn.execute(
                        'UPDATE grocery_deals SET store_id = $1 WHERE store_id = $2',
                        keep_store_id, delete_store_id
                    )
                    print(f"✅ Updated {delete_deals_count} deals to point to store {keep_store_id}")
                
                # Delete the duplicate store
                await conn.execute('DELETE FROM stores WHERE id = $1', delete_store_id)
                print(f"✅ Deleted store {delete_store_id} ('{delete_store['name']}')")
                
                return True
                
    except Exception as e:
        print(f"❌ Error consolidating stores: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await close_pool()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Consolidate duplicate store entries')
    parser.add_argument('--keep', type=int, required=True, help='Store ID to keep')
    parser.add_argument('--delete', type=int, required=True, help='Store ID to delete')
    parser.add_argument('--execute', action='store_true', help='Actually perform the consolidation (default is dry-run)')
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        print("🔍 Running in DRY RUN mode (use --execute to actually make changes)\n")
    else:
        print("⚠️  EXECUTING consolidation - this will modify the database!\n")
    
    success = await consolidate_stores(args.keep, args.delete, dry_run=dry_run)
    
    if success:
        if dry_run:
            print("\n✅ Dry run completed successfully. Use --execute to perform the consolidation.")
        else:
            print("\n✅ Consolidation completed successfully!")
    else:
        print("\n❌ Consolidation failed!")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())

