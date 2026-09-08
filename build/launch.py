"""PyInstaller entry point.

sidecar/main.py cannot be the entry script itself: it uses relative imports
("from . import pipeline"), and a script run as __main__ has no package, so
those raise ImportError before anything else happens. This module is outside
the package and imports it by name, which is the only ordering that works.
"""

from sidecar.main import main

if __name__ == "__main__":
    main()
