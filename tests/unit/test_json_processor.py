"""Tests for JSON processor."""

import sys
import os
import json
from pathlib import Path
from datetime import date
from decimal import Decimal
import pytest

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from groceries.models.grocery import GroceryDeal
from groceries.utils.json_processor import JSONProcessor


@pytest.mark.asyncio
async def test_save_and_load_deal_json():
    """Test saving and loading a deal JSON file."""
    processor = JSONProcessor()
    
    # Create a test deal
    deal = GroceryDeal(
        store_id=1,
        product_name="Organic Milk",
        regular_price=Decimal("5.99"),
        sale_price=Decimal("4.99"),
        unit="gallon",
        quantity=Decimal("1"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7),
        description="Organic whole milk on sale"
    )
    
    # Save to JSON
    output_path = await processor.save_deal_json(deal, subdirectory="test")
    
    # Check file exists
    assert os.path.exists(output_path)
    
    # Check filename is UUID format
    filename = Path(output_path).name
    assert filename.endswith('.json')
    uuid_part = filename[:-5]
    assert len(uuid_part) == 36
    assert uuid_part.count('-') == 4
    
    # Load from JSON
    loaded_data = await processor.load_deal_json(output_path)
    
    # Verify data
    assert loaded_data['product_name'] == "Organic Milk"
    assert loaded_data['store_id'] == 1
    # JSON may load Decimal as float or string depending on serialization
    regular_price = float(loaded_data['regular_price']) if isinstance(loaded_data['regular_price'], str) else loaded_data['regular_price']
    sale_price = float(loaded_data['sale_price']) if isinstance(loaded_data['sale_price'], str) else loaded_data['sale_price']
    assert abs(regular_price - 5.99) < 0.01
    assert abs(sale_price - 4.99) < 0.01
    assert loaded_data['unit'] == "gallon"
    assert loaded_data['valid_from'] == "2025-01-01"
    assert loaded_data['valid_to'] == "2025-01-07"
    assert 'uuid' in loaded_data
    
    # Clean up
    os.remove(output_path)
    test_dir = Path(output_path).parent
    if test_dir.exists() and not os.listdir(test_dir):
        os.rmdir(test_dir)


@pytest.mark.asyncio
async def test_validate_deal_json():
    """Test JSON validation."""
    processor = JSONProcessor()
    
    # Create a test deal
    deal = GroceryDeal(
        store_id=1,
        product_name="Organic Milk",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    # Save to JSON
    output_path = await processor.save_deal_json(deal, subdirectory="test")
    
    # Validate
    is_valid = await processor.validate_deal_json(output_path)
    assert is_valid is True
    
    # Clean up
    os.remove(output_path)
    test_dir = Path(output_path).parent
    if test_dir.exists() and not os.listdir(test_dir):
        os.rmdir(test_dir)


@pytest.mark.asyncio
async def test_get_all_json_files():
    """Test getting all JSON files from a directory."""
    processor = JSONProcessor()
    
    # Create test directory and files
    test_dir = Path("data/stage/test_json_files")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Create some test JSON files
    test_file1 = test_dir / "test1.json"
    test_file2 = test_dir / "test2.json"
    
    with open(test_file1, 'w') as f:
        json.dump({"test": 1}, f)
    with open(test_file2, 'w') as f:
        json.dump({"test": 2}, f)
    
    # Get all JSON files
    json_files = await processor.get_all_json_files(str(test_dir))
    
    # Should find both files
    assert len(json_files) == 2
    assert any("test1.json" in f for f in json_files)
    assert any("test2.json" in f for f in json_files)
    
    # Clean up
    os.remove(test_file1)
    os.remove(test_file2)
    os.rmdir(test_dir)

