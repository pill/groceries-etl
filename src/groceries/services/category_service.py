"""Category service for database operations."""

from typing import Optional
from ..database import get_pool
from ..models.grocery import Category


class CategoryService:
    """Service for category database operations."""
    
    @staticmethod
    async def get_or_create_category(
        name: str,
        parent_category_id: Optional[int] = None,
        conn=None
    ) -> Optional[Category]:
        """Get or create a category. If conn is provided, uses that connection."""
        if not name or not name.strip():
            return None
        
        # Use provided connection or get new one
        if conn:
            return await CategoryService._get_or_create_category_with_conn(conn, name, parent_category_id)
        
        pool = await get_pool()
        try:
            async with pool.acquire() as conn:
                return await CategoryService._get_or_create_category_with_conn(conn, name, parent_category_id)
        except Exception as e:
            print(f"Error creating category '{name}': {str(e)}")
            return None
    
    @staticmethod
    async def _get_or_create_category_with_conn(conn, name: str, parent_category_id: Optional[int]) -> Optional[Category]:
        """Internal method to get or create category with a specific connection."""
        try:
            # First try to find existing category
            query = "SELECT * FROM categories WHERE name = $1"
            row = await conn.fetchrow(query, name)
            
            if row:
                return Category(
                    id=row['id'],
                    name=row['name'],
                    parent_category_id=row['parent_category_id'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            
            # Create new category
            query = """
                INSERT INTO categories (name, parent_category_id)
                VALUES ($1, $2)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING *
            """
            
            row = await conn.fetchrow(query, name, parent_category_id)
            
            if not row:
                return None
            
            return Category(
                id=row['id'],
                name=row['name'],
                parent_category_id=row['parent_category_id'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        except Exception as e:
            print(f"Error in _get_or_create_category_with_conn '{name}': {str(e)}")
            return None
    
    @staticmethod
    async def get_by_id(category_id: int) -> Optional[Category]:
        """Get category by ID."""
        pool = await get_pool()
        query = "SELECT * FROM categories WHERE id = $1"
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, category_id)
            
            if not row:
                return None
            
            return Category(
                id=row['id'],
                name=row['name'],
                parent_category_id=row['parent_category_id'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

