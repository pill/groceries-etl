"""Store service for database operations."""

from typing import Optional
from ..database import get_pool
from ..models.grocery import Store


class StoreService:
    """Service for store database operations."""
    
    @staticmethod
    async def get_or_create_store(
        name: str,
        location: Optional[str] = None,
        website: Optional[str] = None,
        conn=None
    ) -> Optional[Store]:
        """Get or create a store. If conn is provided, uses that connection."""
        if not name or not name.strip():
            return None
        
        # Use provided connection or get new one
        if conn:
            return await StoreService._get_or_create_store_with_conn(conn, name, location, website)
        
        pool = await get_pool()
        try:
            async with pool.acquire() as conn:
                return await StoreService._get_or_create_store_with_conn(conn, name, location, website)
        except Exception as e:
            print(f"Error creating store '{name}': {str(e)}")
            return None
    
    @staticmethod
    async def _get_or_create_store_with_conn(conn, name: str, location: Optional[str], website: Optional[str]) -> Optional[Store]:
        """Internal method to get or create store with a specific connection."""
        try:
            # First try to find existing store
            query = "SELECT * FROM stores WHERE name = $1"
            row = await conn.fetchrow(query, name)
            
            if row:
                return Store(
                    id=row['id'],
                    name=row['name'],
                    location=row['location'],
                    website=row['website'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            
            # Create new store
            query = """
                INSERT INTO stores (name, location, website)
                VALUES ($1, $2, $3)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING *
            """
            
            row = await conn.fetchrow(query, name, location, website)
            
            if not row:
                return None
            
            return Store(
                id=row['id'],
                name=row['name'],
                location=row['location'],
                website=row['website'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        except Exception as e:
            print(f"Error in _get_or_create_store_with_conn '{name}': {str(e)}")
            return None
    
    @staticmethod
    async def get_by_id(store_id: int) -> Optional[Store]:
        """Get store by ID."""
        pool = await get_pool()
        query = "SELECT * FROM stores WHERE id = $1"
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, store_id)
            
            if not row:
                return None
            
            return Store(
                id=row['id'],
                name=row['name'],
                location=row['location'],
                website=row['website'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
    
    @staticmethod
    async def update_store(
        store_id: int,
        name: Optional[str] = None,
        location: Optional[str] = None,
        website: Optional[str] = None
    ) -> Optional[Store]:
        """Update store information."""
        pool = await get_pool()
        
        # Build update query dynamically based on provided fields
        updates = []
        params = []
        param_num = 1
        
        if name is not None:
            updates.append(f"name = ${param_num}")
            params.append(name)
            param_num += 1
        
        if location is not None:
            updates.append(f"location = ${param_num}")
            params.append(location)
            param_num += 1
        
        if website is not None:
            updates.append(f"website = ${param_num}")
            params.append(website)
            param_num += 1
        
        if not updates:
            # No updates provided, just return the current store
            return await StoreService.get_by_id(store_id)
        
        # Add store_id as the last parameter
        params.append(store_id)
        
        query = f"""
            UPDATE stores
            SET {', '.join(updates)}
            WHERE id = ${param_num}
            RETURNING *
        """
        
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            
            if not row:
                return None
            
            return Store(
                id=row['id'],
                name=row['name'],
                location=row['location'],
                website=row['website'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )

