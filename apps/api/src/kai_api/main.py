"""ASGI entrypoint: uvicorn kai_api.main:app"""

from kai_api.app import create_app

app = create_app()
