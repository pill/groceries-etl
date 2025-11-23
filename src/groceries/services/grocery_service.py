"""Grocery service for database operations."""

from typing import List, Optional, Dict, Any
from datetime import date
from decimal import Decimal
from ..database import get_pool
from ..models.grocery import GroceryDeal, GroceryDealFilters, Store, Category
from .store_service import StoreService
from .category_service import CategoryService
from ..utils.uuid_utils import generate_grocery_deal_uuid


class GroceryService:
    """Service for grocery deal database operations."""
    
    @staticmethod
    async def create(deal: GroceryDeal) -> Optional[GroceryDeal]:
        """Create a new grocery deal."""
        pool = await get_pool()
        
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Generate deterministic UUID if not already set
                    if not deal.uuid:
                        deal.uuid = generate_grocery_deal_uuid(
                            deal.product_name,
                            deal.store_id,
                            deal.valid_from,
                            deal.valid_to
                        )
                    
                    # Calculate discount percentage if not provided
                    if deal.discount_percentage is None and deal.regular_price and deal.sale_price:
                        discount = ((deal.regular_price - deal.sale_price) / deal.regular_price) * 100
                        deal.discount_percentage = Decimal(str(round(float(discount), 2)))
                    
                    # Insert the deal
                    deal_query = """
                        INSERT INTO grocery_deals (
                            uuid, store_id, product_name, category_id, regular_price,
                            sale_price, unit, quantity, discount_percentage,
                            valid_from, valid_to, source_url, image_url, description
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        RETURNING *
                    """
                    
                    deal_values = [
                        deal.uuid,
                        deal.store_id,
                        deal.product_name,
                        deal.category_id,
                        deal.regular_price,
                        deal.sale_price,
                        deal.unit,
                        deal.quantity,
                        deal.discount_percentage,
                        deal.valid_from,
                        deal.valid_to,
                        deal.source_url,
                        deal.image_url,
                        deal.description
                    ]
                    
                    try:
                        deal_row = await conn.fetchrow(deal_query, *deal_values)
                    except Exception as insert_error:
                        error_msg = str(insert_error)
                        # Check if it's a duplicate UUID error
                        if 'duplicate key' in error_msg.lower() and 'uuid' in error_msg.lower():
                            print(f"Warning: Deal '{deal.product_name[:50]}' has duplicate UUID {deal.uuid}. Skipping.")
                            # Try to fetch existing deal with this UUID
                            existing = await conn.fetchrow('SELECT * FROM grocery_deals WHERE uuid = $1', deal.uuid)
                            if existing:
                                print(f"  Existing deal: '{existing['product_name'][:50]}' (ID: {existing['id']})")
                        else:
                            print(f"Error: Failed to insert deal '{deal.product_name[:50]}': {type(insert_error).__name__}: {error_msg}")
                        return None
                    
                    if not deal_row:
                        print(f"Error: Deal insert succeeded but returned no row for '{deal.product_name[:50]}'")
                        return None
                    
                    deal_id = deal_row['id']
            
            # Transaction is now committed - fetch the complete deal
            created_deal = await GroceryService.get_by_id(deal_id)
            if not created_deal:
                print(f"Warning: Deal {deal_id} created but couldn't fetch it back")
                deal.id = deal_id
                return deal
            
            return created_deal
        except Exception as e:
            import traceback
            print(f"Error creating deal '{deal.product_name[:50] if deal.product_name else 'No name'}': {type(e).__name__}: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return None
    
    @staticmethod
    async def get_by_id(deal_id: int) -> Optional[GroceryDeal]:
        """Get deal by ID."""
        pool = await get_pool()
        
        query = """
            SELECT 
                gd.*,
                s.name as store_name,
                s.location as store_location,
                s.website as store_website,
                c.name as category_name,
                c.parent_category_id
            FROM grocery_deals gd
            LEFT JOIN stores s ON gd.store_id = s.id
            LEFT JOIN categories c ON gd.category_id = c.id
            WHERE gd.id = $1
        """
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, deal_id)
            
            if not row:
                return None
            
            return GroceryService._map_db_row_to_deal(row)
    
    @staticmethod
    async def get_by_uuid(uuid: str) -> Optional[GroceryDeal]:
        """Get deal by UUID."""
        pool = await get_pool()
        
        query = """
            SELECT 
                gd.*,
                s.name as store_name,
                s.location as store_location,
                s.website as store_website,
                c.name as category_name,
                c.parent_category_id
            FROM grocery_deals gd
            LEFT JOIN stores s ON gd.store_id = s.id
            LEFT JOIN categories c ON gd.category_id = c.id
            WHERE gd.uuid = $1
        """
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, uuid)
            
            if not row:
                return None
            
            return GroceryService._map_db_row_to_deal(row)
    
    @staticmethod
    async def get_all(filters: Optional[GroceryDealFilters] = None, limit: int = 50, offset: int = 0) -> List[GroceryDeal]:
        """Get all deals with optional filtering."""
        pool = await get_pool()
        
        base_query = 'SELECT DISTINCT gd.id, gd.created_at FROM grocery_deals gd WHERE 1=1'
        values = []
        param_count = 0
        
        if filters:
            if filters.store_id:
                param_count += 1
                base_query += f' AND gd.store_id = ${param_count}'
                values.append(filters.store_id)
            
            if filters.category_id:
                param_count += 1
                base_query += f' AND gd.category_id = ${param_count}'
                values.append(filters.category_id)
            
            if filters.min_discount_percentage:
                param_count += 1
                base_query += f' AND gd.discount_percentage >= ${param_count}'
                values.append(filters.min_discount_percentage)
            
            if filters.max_sale_price:
                param_count += 1
                base_query += f' AND gd.sale_price <= ${param_count}'
                values.append(filters.max_sale_price)
            
            if filters.min_sale_price:
                param_count += 1
                base_query += f' AND gd.sale_price >= ${param_count}'
                values.append(filters.min_sale_price)
            
            if filters.valid_from:
                param_count += 1
                base_query += f' AND gd.valid_to >= ${param_count}'
                values.append(filters.valid_from)
            
            if filters.valid_to:
                param_count += 1
                base_query += f' AND gd.valid_from <= ${param_count}'
                values.append(filters.valid_to)
            
            if filters.product_name_search:
                param_count += 1
                base_query += f" AND to_tsvector('english', gd.product_name) @@ plainto_tsquery('english', ${param_count})"
                values.append(filters.product_name_search)
        
        base_query += f' ORDER BY gd.created_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}'
        values.extend([limit, offset])
        
        # Get deal IDs first
        async with pool.acquire() as conn:
            deal_ids_result = await conn.fetch(base_query, *values)
            deal_ids = [row['id'] for row in deal_ids_result]
            
            if not deal_ids:
                return []
            
            # Now fetch full deals
            query = """
                SELECT 
                    gd.*,
                    s.name as store_name,
                    s.location as store_location,
                    s.website as store_website,
                    c.name as category_name,
                    c.parent_category_id
                FROM grocery_deals gd
                LEFT JOIN stores s ON gd.store_id = s.id
                LEFT JOIN categories c ON gd.category_id = c.id
                WHERE gd.id = ANY($1)
                ORDER BY gd.created_at DESC
            """
            
            rows = await conn.fetch(query, deal_ids)
            
            return [GroceryService._map_db_row_to_deal(row) for row in rows]
    
    @staticmethod
    async def search(search_term: str, limit: int = 50) -> List[GroceryDeal]:
        """Search deals by product name."""
        pool = await get_pool()
        
        # First get deal IDs that match the search
        deal_ids_query = """
            SELECT DISTINCT gd.id FROM grocery_deals gd 
            WHERE to_tsvector('english', gd.product_name || ' ' || COALESCE(gd.description, '')) @@ plainto_tsquery('english', $1)
            ORDER BY ts_rank(to_tsvector('english', gd.product_name || ' ' || COALESCE(gd.description, '')), plainto_tsquery('english', $1)) DESC
            LIMIT $2
        """
        
        async with pool.acquire() as conn:
            deal_ids_result = await conn.fetch(deal_ids_query, search_term, limit)
            deal_ids = [row['id'] for row in deal_ids_result]
            
            if not deal_ids:
                return []
            
            # Now fetch full deals
            query = """
                SELECT 
                    gd.*,
                    s.name as store_name,
                    s.location as store_location,
                    s.website as store_website,
                    c.name as category_name,
                    c.parent_category_id
                FROM grocery_deals gd
                LEFT JOIN stores s ON gd.store_id = s.id
                LEFT JOIN categories c ON gd.category_id = c.id
                WHERE gd.id = ANY($1)
            """
            
            rows = await conn.fetch(query, deal_ids)
            
            return [GroceryService._map_db_row_to_deal(row) for row in rows]
    
    @staticmethod
    async def get_stats() -> Dict[str, Any]:
        """Get deal statistics."""
        pool = await get_pool()
        
        query = """
            SELECT 
                COUNT(*) as total_deals,
                COUNT(DISTINCT store_id) as unique_stores,
                COUNT(DISTINCT category_id) as unique_categories,
                AVG(discount_percentage) as avg_discount,
                AVG(sale_price) as avg_sale_price,
                MIN(valid_from) as earliest_deal,
                MAX(valid_to) as latest_deal
            FROM grocery_deals
        """
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query)
            return dict(row)
    
    @staticmethod
    def _map_db_row_to_deal(row: Any) -> GroceryDeal:
        """Helper method to map database row to GroceryDeal object."""
        deal = GroceryDeal(
            id=row['id'],
            uuid=str(row['uuid']),
            store_id=row['store_id'],
            product_name=row['product_name'],
            category_id=row['category_id'],
            regular_price=row['regular_price'],
            sale_price=row['sale_price'],
            unit=row['unit'],
            quantity=row['quantity'],
            discount_percentage=row['discount_percentage'],
            valid_from=row['valid_from'],
            valid_to=row['valid_to'],
            source_url=row['source_url'],
            image_url=row['image_url'],
            description=row['description'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
        
        # Add populated store data if available
        if row['store_name']:
            deal.store = Store(
                id=row['store_id'],
                name=row['store_name'],
                location=row['store_location'],
                website=row['store_website']
            )
        
        # Add populated category data if available
        if row['category_name']:
            deal.category = Category(
                id=row['category_id'],
                name=row['category_name'],
                parent_category_id=row['parent_category_id']
            )
        
        return deal

