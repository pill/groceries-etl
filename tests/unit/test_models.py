"""Tests for grocery models."""

import sys
from pathlib import Path
from datetime import date
from decimal import Decimal
import pytest

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from groceries.models.grocery import GroceryDeal, Store, Category, GroceryDealFilters


def test_store_model():
    """Test Store model creation."""
    store = Store(
        name="Stop and Shop",
        location="New York",
        website="https://www.stopandshop.com"
    )
    
    assert store.name == "Stop and Shop"
    assert store.location == "New York"
    assert store.website == "https://www.stopandshop.com"


def test_category_model():
    """Test Category model creation."""
    category = Category(
        name="Produce",
        parent_category_id=None
    )
    
    assert category.name == "Produce"
    assert category.parent_category_id is None


def test_grocery_deal_model():
    """Test GroceryDeal model creation."""
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
    
    assert deal.store_id == 1
    assert deal.product_name == "Organic Milk"
    assert deal.regular_price == Decimal("5.99")
    assert deal.sale_price == Decimal("4.99")
    assert deal.unit == "gallon"
    assert deal.quantity == Decimal("1")
    assert deal.valid_from == date(2025, 1, 1)
    assert deal.valid_to == date(2025, 1, 7)
    assert deal.description == "Organic whole milk on sale"


def test_grocery_deal_filters():
    """Test GroceryDealFilters model creation."""
    filters = GroceryDealFilters(
        store_id=1,
        category_id=2,
        min_discount_percentage=Decimal("10.0"),
        max_sale_price=Decimal("5.00")
    )
    
    assert filters.store_id == 1
    assert filters.category_id == 2
    assert filters.min_discount_percentage == Decimal("10.0")
    assert filters.max_sale_price == Decimal("5.00")


def test_grocery_deal_with_store():
    """Test GroceryDeal with populated store."""
    store = Store(name="Stop and Shop")
    deal = GroceryDeal(
        store_id=1,
        product_name="Organic Milk",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7),
        store=store
    )
    
    assert deal.store is not None
    assert deal.store.name == "Stop and Shop"


def test_grocery_deal_with_category():
    """Test GroceryDeal with populated category."""
    category = Category(name="Dairy")
    deal = GroceryDeal(
        store_id=1,
        product_name="Organic Milk",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 1, 7),
        category=category
    )
    
    assert deal.category is not None
    assert deal.category.name == "Dairy"

