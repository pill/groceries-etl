"""Grocery data models."""

from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class Store(BaseModel):
    """Store model."""
    
    id: Optional[int] = None
    name: str
    location: Optional[str] = None
    website: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Category(BaseModel):
    """Category model."""
    
    id: Optional[int] = None
    name: str
    parent_category_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GroceryDeal(BaseModel):
    """Grocery deal model."""
    
    id: Optional[int] = None
    uuid: Optional[str] = None
    store_id: int
    product_name: str
    category_id: Optional[int] = None
    regular_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    unit: Optional[str] = None  # e.g., 'lb', 'oz', 'each', 'pack'
    quantity: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    valid_from: date
    valid_to: date
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Populated fields when joining with stores and categories
    store: Optional[Store] = None
    category: Optional[Category] = None


class GroceryDealFilters(BaseModel):
    """Grocery deal filtering options."""
    
    store_id: Optional[int] = None
    category_id: Optional[int] = None
    min_discount_percentage: Optional[Decimal] = None
    max_sale_price: Optional[Decimal] = None
    min_sale_price: Optional[Decimal] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    product_name_search: Optional[str] = None

