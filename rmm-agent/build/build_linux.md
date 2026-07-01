# Linux build — rmm-agent

    pip install -r requirements.txt
    pyinstaller rmm-agent.spec
    # result: dist/rmm-agent (single ELF executable)

Test it:
    ./dist/rmm-agent --headless --token <token> --server ws://localhost:8765 -v

Screen capture needs an X11 session (not Wayland). The tray icon needs a desktop
session; on a headless box use --headless.