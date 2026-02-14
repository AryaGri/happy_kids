"""
Единое десктопное приложение. Точка входа для run_desktop.bat.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app import main

if __name__ == "__main__":
    main()
