"""UUID utilities for grocery deal tracking."""

import uuid
from datetime import date


# Namespace for grocery deal UUIDs (using DNS namespace as base)
GROCERY_DEAL_UUID_NAMESPACE = uuid.UUID('6ba7b811-9dad-11d1-80b4-00c04fd430c8')


def generate_grocery_deal_uuid(
    product_name: str,
    store_id: int,
    valid_from: date,
    valid_to: date
) -> str:
    """
    Generate a deterministic UUID for a grocery deal.
    
    This ensures that:
    - Same product from same store with same dates always gets the same UUID
    - Can deduplicate deals across different pipeline stages
    - UUIDs are consistent across system restarts and reprocessing
    
    Args:
        product_name: Product name (required)
        store_id: Store ID (required)
        valid_from: Deal start date (required)
        valid_to: Deal end date (required)
    
    Returns:
        String representation of UUID
        
    Example:
        >>> from datetime import date
        >>> generate_grocery_deal_uuid("Organic Milk", 1, date(2025, 1, 1), date(2025, 1, 7))
        '550e8400-e29b-41d4-a716-446655440000'
        
        >>> generate_grocery_deal_uuid("Organic Milk", 1, date(2025, 1, 1), date(2025, 1, 7))
        '550e8400-e29b-41d4-a716-446655440000'  # Same UUID!
    """
    # Normalize product name (lowercase, strip whitespace)
    normalized_product = product_name.strip().lower()
    
    # Create content string for UUID generation
    content = f"{normalized_product}:{store_id}:{valid_from}:{valid_to}"
    
    # Generate deterministic UUID using uuid5
    return str(uuid.uuid5(GROCERY_DEAL_UUID_NAMESPACE, content))

