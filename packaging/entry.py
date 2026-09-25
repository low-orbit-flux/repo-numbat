"""PyInstaller entry point: always start the GUI."""
import sys

from repo_numbat.cli import main

if "--cli" in sys.argv[1:] and sys.platform == "win32":
    print("--cli is not available in the packaged app; use scripts\\repo-numbat.bat --cli")
raise SystemExit(main())
