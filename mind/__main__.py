"""python -m mind   (from the dashboard folder)"""
from .server import serve

if __name__ == "__main__":
    try:
        serve()
    except KeyboardInterrupt:
        pass
