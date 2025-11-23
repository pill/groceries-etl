# groceries-etl

Data ingestion for weekly grocery deals. Scrape grocery store deals, transform to structured JSON, and load into PostgreSQL.

## 🚀 Quick Start

### Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your database credentials

# Start services
docker-compose up -d
```

**Note:** When running CLI commands, you have two options:

**Option 1: Use the wrapper script (recommended)**
```bash
./groceries test-db
./groceries load-directory data/stage/hmart
```

**Option 2: Set PYTHONPATH manually**
```bash
export PYTHONPATH=src:$PYTHONPATH
python -m groceries.cli test-db
python -m groceries.cli load-directory data/stage/hmart
```

### Test Setup

```bash
# Test database connection
python -m groceries.cli test-db
```

## 🎯 Core Features

- **Web Scraping**: Framework for scraping weekly deals from grocery stores
- **Structured JSON**: Transform scraped data to structured JSON format
- **PostgreSQL Database**: Relational storage with full schema
- **UUID Tracking**: Track deals through entire pipeline with unique identifiers
- **CLI Interface**: Easy command-line tools
- **Docker Support**: Complete containerization

## 📖 Usage Guide

### Scrape Deals

Scrape deals from stores (implement store-specific scrapers):

```bash
# Scrape a specific store
python -m groceries.cli scrape --store "Stop and Shop"

# Scrape all stores
python -m groceries.cli scrape --all
```

### Load Deals to Database

After scraping, deals are saved as JSON files in `data/stage/`. Load them into the database:

**Load a single deal:**
```bash
python -m groceries.cli load-deal data/stage/hmart/abc123-uuid.json
```

**Load all deals from a directory (recommended):**
```bash
# Load all JSON files from a specific directory
python -m groceries.cli load-directory data/stage/hmart

# Load all JSON files from all subdirectories
python -m groceries.cli load-directory data/stage

# Dry run to validate files without loading
python -m groceries.cli load-directory data/stage/hmart --dry-run

# Verbose output to see each file
python -m groceries.cli load-directory data/stage/hmart --verbose
```

**Or use the script directly:**
```bash
python scripts/processing/load_json_to_db.py --directory data/stage/hmart
python scripts/processing/load_json_to_db.py --directory data/stage/hmart --dry-run
python scripts/processing/load_json_to_db.py --directory data/stage/hmart --verbose
```

### View Deals

```bash
# List recent deals
python -m groceries.cli list-deals --limit 10

# Search for deals
python -m groceries.cli search "organic milk"

# View statistics
python -m groceries.cli stats
```

## 🏗️ Architecture

### Data Flow

1. **Scrape** → Raw grocery deal data (from web scraping)
2. **Transform** → Structured JSON (using Pydantic models)
3. **Load** → PostgreSQL database

### Project Structure

```
groceries-etl/
├── src/groceries/          # Main Python package
│   ├── models/             # Pydantic data models
│   ├── services/           # Business logic (DB, scrapers)
│   ├── database/           # Database connection & queries
│   ├── utils/              # Utility functions
│   ├── cli/                # Command-line interface
│   └── config.py           # Configuration management
├── scripts/                # Setup & utility scripts
│   └── processing/        # Scraping scripts
├── data/                   # Data directories
│   ├── raw/                # Raw scraped data
│   └── stage/              # Processed JSON files
├── db/                     # Database files
│   ├── schema.sql          # PostgreSQL schema
│   └── init-db.sql         # Database initialization
└── docker-compose.yml      # Docker configuration
```

## 🛠️ Tech Stack

### Backend (Python)
- **Python 3.11+** - Modern Python with async/await
- **Pydantic** - Runtime type validation and schema management
- **asyncpg** - High-performance PostgreSQL driver
- **BeautifulSoup4** - Web scraping
- **httpx** - Async HTTP client
- **click** - CLI framework

### Data & Infrastructure
- **PostgreSQL 15** - Relational database
- **Docker** - Containerization and deployment

## 📋 CLI Commands

### Database Operations
```bash
./groceries test-db          # Test database connection
./groceries list-deals       # List recent deals
./groceries search "milk"    # Search deals
./groceries stats            # Show statistics
```

### Deal Processing
```bash
./groceries load-deal <json-file>  # Load deal JSON to database
./groceries load-directory data/stage/hmart  # Load all JSON files from directory
./groceries scrape --store "Store Name"  # Scrape deals
```

**Alternative:** If you prefer using `python -m groceries.cli`, set PYTHONPATH first:
```bash
export PYTHONPATH=src:$PYTHONPATH
python -m groceries.cli <command>
```

## 🐳 Docker Setup

### Start All Services
```bash
docker-compose up -d
```

This starts:
- PostgreSQL database
- pgAdmin (optional, at http://localhost:8080)

### Service-Specific Commands
```bash
# Start only database
docker-compose up -d postgres

# View logs
docker-compose logs -f postgres

# Stop all services
docker-compose down
```

## 📊 Database Schema

### Tables
- **stores**: Store information (name, location, website)
- **categories**: Product categories
- **grocery_deals**: Deal information (product, prices, dates, store, category)

### Key Features
- UUID-based deduplication
- Full-text search on product names
- Date range indexing for efficient queries
- Automatic timestamp management

## 🔄 Workflows

### Deal Extraction Pipeline

1. **Scrape**: Use store-specific scrapers to collect deal data
2. **Transform**: Convert to structured GroceryDeal objects
3. **Save JSON**: Store as JSON files with UUID filenames
4. **Load**: Insert into PostgreSQL database
5. **Query**: Search and filter deals

## 📝 Creating Store-Specific Scrapers

To create a scraper for a new store:

1. Create a new scraper class in `scripts/processing/`:
```python
from scripts.processing.base_scraper import BaseGroceryScraper
from groceries.models.grocery import GroceryDeal

class MyStoreScraper(BaseGroceryScraper):
    async def scrape_deals(self) -> list[GroceryDeal]:
        # Implement your scraping logic here
        deals = []
        # ... scraping code ...
        return deals
```

2. Add it to `scrape_grocery_deals.py` or create a separate script

## 🆘 Troubleshooting

### Common Issues

**Virtual environment not activated:**
```bash
source venv/bin/activate  # or poetry shell
```

**Database connection failed:**
```bash
docker-compose up -d postgres
python -m groceries.cli test-db
```

**Import errors:**
```bash
# Make sure you're in the project root
# Install dependencies
pip install -r requirements.txt
```

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Modeled after the recipes-etl project architecture
- Python async/await patterns
- PostgreSQL and Docker ecosystems


## Inspiration Apps

- https://www.anylist.com/
    - create grocery list 
    - send to services like amazon fresh
    - shared grocery lists
    - manage recipes

- https://www.mealime.com/
    - another recipe/grocery list app, personalized

