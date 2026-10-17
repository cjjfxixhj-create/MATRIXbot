#!/usr/bin/env python3
"""Installs the matrixbot library from GitHub using pip.

Run it with:  python3 install.py
Works on Windows, Linux and Android (Pydroid / Termux).
"""
import subprocess
import sys

REPO = "git+https://github.com/cjjfxixhj-create/MATRIXbot.git"


def main():
    print("Installing matrixbot from GitHub ...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", REPO]
    )
    print("\nDone! Now you can use it:")
    print("    from matrixbot import MatrixBot")
    print('    bot = MatrixBot("YOUR_TOKEN")')


if __name__ == "__main__":
    main()
