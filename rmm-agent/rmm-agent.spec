name: Build Agent

on:
  workflow_dispatch:
  push:
    tags:
      - "agent-v*"

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            artifact: rmm-agent-windows
          - os: macos-latest
            artifact: rmm-agent-mac
          - os: ubuntu-latest
            artifact: rmm-agent-linux
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        working-directory: rmm-agent
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install Linux system libraries
        if: matrix.os == 'ubuntu-latest'
        run: |
          sudo apt-get update
          sudo apt-get install -y python3-dev libgirepository1.0-dev gcc pkg-config libcairo2-dev gir1.2-gtk-3.0 libgtk-3-dev
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt || true
          pip install pyinstaller mss pillow psutil websockets plyer
      - name: Build agent
        run: pyinstaller rmm-agent.spec
      - name: Bundle config with the build
        shell: bash
        run: cp config.json dist/ 2>/dev/null || true
      - name: Upload
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: rmm-agent/dist/*
          if-no-files-found: ignore