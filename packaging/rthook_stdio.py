# PyInstaller runtime hook: GUI subsystem has sys.stdout is None before app code.
import os
import sys

if sys.stdout is None:
    sys.stdout = sys.__stdout__ = open(os.devnull, "w", encoding="utf-8", errors="replace")
if sys.stderr is None:
    sys.stderr = sys.__stderr__ = open(os.devnull, "w", encoding="utf-8", errors="replace")
if sys.stdin is None:
    sys.stdin = sys.__stdin__ = open(os.devnull, "r", encoding="utf-8", errors="replace")
