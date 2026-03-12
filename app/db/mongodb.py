"""
db/mongodb.py — Single place that owns the MongoDB connection.
Motor is the async MongoDB driver. We use it so FastAPI never blocks
waiting for a DB response (it can handle other requests while waiting).
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

# Module-level client — created once at startup, reused for every request.
_client: AsyncIOMotorClient = None


def get_client() -> AsyncIOMotorClient:
    """Return the shared Motor client (singleton pattern)."""
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI is not set in your .env file")
        _client = AsyncIOMotorClient(uri)
    return _client


def get_database():
    """Return the database object. Collections are accessed as attributes."""
    db_name = os.getenv("MONGODB_DB_NAME", "adaptive_engine")
    return get_client()[db_name]


async def close_connection():
    """Called on app shutdown to cleanly close the connection pool."""
    global _client
    if _client:
        _client.close()
        _client = None
