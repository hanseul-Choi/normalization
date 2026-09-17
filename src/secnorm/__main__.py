"""Entrypoint for `python -m secnorm`."""

import sys
from secnorm.cli import main

if __name__ == "__main__":
    sys.exit(main())
