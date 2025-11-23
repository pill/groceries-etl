"""Setup script for groceries-etl package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="groceries-etl",
    version="1.0.0",
    description="Weekly grocery deals ETL pipeline",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "asyncpg>=0.29.0",
        "pydantic>=2.5.0",
        "python-dotenv>=1.0.0",
        "click>=8.1.0",
        "aiofiles>=23.2.0",
        "httpx>=0.25.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=5.0.0",
    ],
    entry_points={
        "console_scripts": [
            "groceries=groceries.cli.commands:main",
        ],
    },
)

