"""PyInstaller entry point.

PyInstaller needs a script (not a module) as its entry. This just calls the
agent's main(). Build with:  pyinstaller rmm-agent.spec
"""
from agent.main import main

if __name__ == "__main__":
    raise SystemExit(main())