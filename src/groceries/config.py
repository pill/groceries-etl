"""Configuration management for the groceries application."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseConfig:
    """Database configuration."""
    
    def __init__(self):
        self.user = os.getenv('DB_USER', 'postgres')
        self.host = os.getenv('DB_HOST', 'localhost')
        self.database = os.getenv('DB_NAME', 'groceries')
        self.password = os.getenv('DB_PASSWORD', 'postgres')
        self.port = int(os.getenv('DB_PORT', '5432'))


class AppConfig:
    """Application configuration."""
    
    def __init__(self):
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'


# Global configuration instances
db_config = DatabaseConfig()
app_config = AppConfig()

