import sys
from pathlib import Path

# Package folder name contains hyphens, so can't be imported as a regular package.
# Add the package directory to sys.path so tests can import node modules directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
