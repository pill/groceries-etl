"""Main entry point for groceries package."""

import sys
from pathlib import Path

# Add src directory to path so imports work
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_PATH = PROJECT_ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from groceries.cli.commands import main

if __name__ == '__main__':
    main()

