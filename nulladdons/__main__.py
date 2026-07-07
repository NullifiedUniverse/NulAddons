"""Enable ``python -m nulladdons``."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
