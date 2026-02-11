"""Allow running the scraper as python -m scraper."""
from scraper.scraper import main
import sys

if __name__ == "__main__":
    main()
    sys.exit(0)
