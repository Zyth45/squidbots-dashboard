"""Start the mind service:  python run-mind.py

A script rather than `python -m mind` because the repack's embedded Python does not put the current folder on
sys.path, so a package next to the script is not found unless the script adds it (as squidbots.py does).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from mind.server import serve  # noqa: E402

if __name__ == "__main__":
    try:
        serve()
    except KeyboardInterrupt:
        pass
