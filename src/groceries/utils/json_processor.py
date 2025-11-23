"""JSON processing utilities."""

import json
import os
from typing import Dict, Any, Optional
from datetime import date
from decimal import Decimal
import aiofiles
from ..models.grocery import GroceryDeal
from ..utils.uuid_utils import generate_grocery_deal_uuid


class JSONProcessor:
    """JSON processor for grocery deal data."""
    
    async def save_deal_json(
        self,
        deal: GroceryDeal,
        subdirectory: Optional[str] = None
    ) -> str:
        """Save grocery deal data to a JSON file with deterministic UUID.
        
        Args:
            deal: GroceryDeal object containing deal data
            subdirectory: Optional subdirectory within data/stage/
        
        Returns:
            Path to the saved JSON file
        """
        # Create output directory if it doesn't exist
        if subdirectory:
            output_dir = os.path.join("data/stage", subdirectory)
        else:
            output_dir = "data/stage"
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert to dict first
        deal_dict = deal.model_dump(mode='json')
        
        # Generate deterministic UUID if not already set
        if not deal.uuid:
            uuid = generate_grocery_deal_uuid(
                deal.product_name,
                deal.store_id,
                deal.valid_from,
                deal.valid_to
            )
            deal_dict['uuid'] = uuid
        
        # Use UUID as filename
        output_filename = f"{deal_dict['uuid']}.json"
        output_path = os.path.join(output_dir, output_filename)
        
        # Custom JSON encoder for Decimal and date objects
        def json_serializer(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, date):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        async with aiofiles.open(output_path, 'w', encoding='utf-8') as file:
            await file.write(json.dumps(deal_dict, indent=2, ensure_ascii=False, default=json_serializer))
        
        return output_path
    
    async def load_deal_json(self, json_file_path: str) -> Dict[str, Any]:
        """Load grocery deal data from a JSON file."""
        if not os.path.exists(json_file_path):
            raise FileNotFoundError(f"JSON file not found: {json_file_path}")
        
        try:
            async with aiofiles.open(json_file_path, 'r', encoding='utf-8') as file:
                content = await file.read()
                return json.loads(content)
        except Exception as e:
            raise Exception(f"Error loading JSON file: {str(e)}")
    
    async def validate_deal_json(self, json_file_path: str) -> bool:
        """Validate that a JSON file contains valid grocery deal data."""
        try:
            deal_data = await self.load_deal_json(json_file_path)
            # Validate against Pydantic model
            GroceryDeal.model_validate(deal_data)
            return True
        except Exception:
            return False
    
    async def get_all_json_files(self, directory: str) -> list[str]:
        """Get all JSON files in a directory."""
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        json_files = []
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                json_files.append(os.path.join(directory, filename))
        
        return sorted(json_files)

