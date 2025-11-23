#!/usr/bin/env python3
"""
Script to update store_id in JSON files.

Usage:
    python scripts/update_store_ids.py --directory data/stage/stew_leonards --old-id 3 --new-id 2
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
import argparse

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

import aiofiles


async def update_json_file(file_path: Path, old_store_id: int, new_store_id: int, dry_run: bool = False) -> bool:
    """Update store_id in a single JSON file."""
    try:
        # Read the file
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        
        data = json.loads(content)
        
        # Check if store_id needs updating
        if data.get('store_id') != old_store_id:
            return False  # No update needed
        
        # Update store_id
        data['store_id'] = new_store_id
        
        if not dry_run:
            # Write back to file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        
        return True
    except Exception as e:
        print(f"  ❌ Error updating {file_path.name}: {e}")
        return False


async def update_directory(directory: str, old_store_id: int, new_store_id: int, dry_run: bool = False):
    """Update store_id in all JSON files in a directory."""
    dir_path = Path(directory)
    
    if not dir_path.exists():
        print(f"❌ Directory not found: {directory}")
        return
    
    # Find all JSON files
    json_files = sorted(dir_path.glob('*.json'))
    
    if not json_files:
        print(f"❌ No JSON files found in {directory}")
        return
    
    print(f"📊 Found {len(json_files)} JSON files")
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    print(f"🔄 Updating store_id from {old_store_id} to {new_store_id}")
    print()
    
    updated = 0
    skipped = 0
    failed = 0
    
    for idx, json_file in enumerate(json_files, 1):
        if idx % 10 == 0 or idx == len(json_files):
            print(f"[{idx}/{len(json_files)}] Processing: {json_file.name}")
        
        success = await update_json_file(json_file, old_store_id, new_store_id, dry_run=dry_run)
        
        if success:
            updated += 1
        else:
            # Check if it was skipped (already correct) or failed
            try:
                async with aiofiles.open(json_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                data = json.loads(content)
                if data.get('store_id') == new_store_id:
                    skipped += 1
                else:
                    failed += 1
            except:
                failed += 1
    
    print()
    print("=" * 60)
    print("📊 Summary:")
    print(f"  ✅ Updated: {updated}")
    print(f"  ℹ️  Skipped (already correct): {skipped}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📁 Total files: {len(json_files)}")
    print("=" * 60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Update store_id in JSON files',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--directory',
        type=str,
        required=True,
        help='Directory containing JSON files to update'
    )
    parser.add_argument(
        '--old-id',
        type=int,
        required=True,
        help='Old store_id value to replace'
    )
    parser.add_argument(
        '--new-id',
        type=int,
        required=True,
        help='New store_id value'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate files without making changes'
    )
    
    args = parser.parse_args()
    
    await update_directory(args.directory, args.old_id, args.new_id, args.dry_run)


if __name__ == '__main__':
    asyncio.run(main())

