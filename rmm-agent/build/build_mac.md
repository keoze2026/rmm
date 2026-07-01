# macOS build — Remote Support Agent.app

Run on a Mac with Python 3.11+ (build on Apple Silicon for arm64, Intel for x86_64).

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pyinstaller rmm-agent.spec

Result: dist/Remote Support Agent.app

Install + auto-start:

    cp -R "dist/Remote Support Agent.app" /Applications/
    sudo ./service/macos/install_agent.sh "wss://<host>:8765" "<token>"

Required once per user (macOS enforces this — capture/control no-op until granted):
  System Settings -> Privacy & Security ->
    * Screen Recording  -> enable "Remote Support Agent"
    * Accessibility     -> enable "Remote Support Agent"

For distribution, codesign + notarize the .app. Not needed for internal use.