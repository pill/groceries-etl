"""Tests for UUID utilities."""

import sys
from pathlib import Path
from datetime import date
import pytest

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from groceries.utils.uuid_utils import generate_grocery_deal_uuid


def test_generate_grocery_deal_uuid():
    """Test UUID generation for grocery deals."""
    uuid1 = generate_grocery_deal_uuid(
        product_name="Organic Milk",
        store_id=1,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    # Should be a valid UUID string
    assert isinstance(uuid1, str)
    assert len(uuid1) == 36
    assert uuid1.count('-') == 4
    
    # Same inputs should generate same UUID (deterministic)
    uuid2 = generate_grocery_deal_uuid(
        product_name="Organic Milk",
        store_id=1,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    assert uuid1 == uuid2


def test_uuid_different_products():
    """Test that different products generate different UUIDs."""
    uuid1 = generate_grocery_deal_uuid(
        product_name="Organic Milk",
        store_id=1,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    uuid2 = generate_grocery_deal_uuid(
        product_name="Organic Eggs",
        store_id=1,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    assert uuid1 != uuid2


def test_uuid_different_stores():
    """Test that different stores generate different UUIDs."""
    uuid1 = generate_grocery_deal_uuid(
        product_name="Organic Milk",
        store_id=1,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    uuid2 = generate_grocery_deal_uuid(
        product_name="Organic Milk",
        store_id=2,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    assert uuid1 != uuid2


def test_uuid_different_dates():
    """Test that different dates generate different UUIDs."""
    uuid1 = generate_grocery_deal_uuid(
        product_name="Organic Milk",
        store_id=1,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    uuid2 = generate_grocery_deal_uuid(
        product_name="Organic Milk",
        store_id=1,
        valid_from=date(2025, 1, 8),
        valid_to=date(2025, 1, 14)
    )
    
    assert uuid1 != uuid2


def test_uuid_case_insensitive():
    """Test that UUID generation is case-insensitive for product names."""
    uuid1 = generate_grocery_deal_uuid(
        product_name="Organic Milk",
        store_id=1,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    uuid2 = generate_grocery_deal_uuid(
        product_name="organic milk",
        store_id=1,
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7)
    )
    
    assert uuid1 == uuid2

