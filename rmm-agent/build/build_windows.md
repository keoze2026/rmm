# Windows build — rmm-agent.exe

Run on a Windows 10/11 machine with Python 3.11+ installed.

    python -m venv .venv
    .\.venv\Scripts\activate
    pip install -r requirements.txt
    pyinstaller rmm-agent.spec

Result: dist\rmm-agent.exe (single file, no console window — tray icon is the UI)

Ship the .exe with a config.json (server_url + that machine's token) in the same
folder. Then register auto-start:

    .\service\windows\install_agent.ps1 -ServerUrl "wss://<host>:8765" -Token "<token>"

Notes:
- SmartScreen may warn on an unsigned .exe. Sign it with signtool for production.
- Use -RunLevel Highest to control UAC/elevated windows on the endpoint.