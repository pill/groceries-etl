"""Database connection management."""

from typing import Optional
import asyncpg
from asyncpg import Pool
from ..config import db_config

# Global connection pool
_pool: Optional[Pool] = None


async def get_pool() -> Pool:
    """Get the database connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            user=db_config.user,
            host=db_config.host,
            database=db_config.database,
            password=db_config.password,
            port=db_config.port,
            min_size=5,
            max_size=30,
            command_timeout=60,
            max_inactive_connection_lifetime=300
        )
    return _pool


async def close_pool():
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def test_connection() -> bool:
    """Test the database connection."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval('SELECT NOW()')
            print('✅ Database connected successfully')
            print(f'📅 Database time: {result}')
            return True
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        return False

