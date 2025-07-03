import os
import json
import logging
from typing import Any, Optional, List

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument, ASCENDING, DESCENDING

load_dotenv()

# Initialize logging
logger = logging.getLogger("database")
logger.setLevel(logging.INFO)

class DataAccessLayer:
    def __init__(self, db_name: Optional[str] = None):
        self.mongo_uri = os.getenv("MONGO_URI")
        self.db_name = db_name or os.getenv("MONGO_DB_NAME")
        if not self.mongo_uri or not self.db_name:
            raise ValueError("MONGO_URI and MONGO_DB_NAME must be set in .env file")

        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
    
    async def connect(self):
        if self.client is None:
            # When this is called, motor binds the client to the current running event loop.
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            logger.info(f"Database connection established (db: {self.db_name}) for loop {id(self.client.get_io_loop())}")
            await self._initialize_indexes()
    
    async def close(self):
        if self.client:
            self.client.close()
            self.client = None
            logger.info("Database connection closed")
            
    async def find(self, collection: str, query: dict = {}, sort: Optional[list] = None, limit: int = 0) -> List[dict]:
        await self.connect()
        cursor = self.db[collection].find(query).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        results = []
        async for doc in cursor:
            doc['_id'] = str(doc['_id'])
            results.append(doc)
        return results

    async def get(self, collection: str, query: dict) -> Optional[dict]:
        await self.connect()
        doc = await self.db[collection].find_one(query)
        if doc:
            doc['_id'] = str(doc['_id'])
            return doc
        return None

    async def create(self, collection: str, data: dict) -> str:
        await self.connect()
        result = await self.db[collection].insert_one(data)
        return str(result.inserted_id)

    async def update(self, collection: str, query: dict, update_data: dict, upsert: bool = False) -> Optional[dict]:
        await self.connect()
        result = await self.db[collection].find_one_and_update(
            query,
            update_data,
            upsert=upsert,
            return_document=ReturnDocument.AFTER
        )
        if result:
            result['_id'] = str(result['_id'])
        return result



    async def delete_many(self, collection: str, query: dict) -> int:
        await self.connect()
        result = await self.db[collection].delete_many(query)
        return result.deleted_count

    async def replace_collection(self, collection: str, data: list):
        await self.connect()
        # This is a transactional operation for atomic replacement
        async with await self.client.start_session() as s:
            async with s.start_transaction():
                await self.db[collection].delete_many({}, session=s)
                if data:
                    await self.db[collection].insert_many(data, session=s)

    async def _initialize_indexes(self):
        try:
            # Use the db instance associated with this DataAccessLayer instance
            await self.db.users.create_index("username", unique=True)
            await self.db.suggestions.create_index([("votes", DESCENDING)])
            await self.db.suggestions.create_index("yt_id", unique=True, sparse=True)
            await self.db.playlist.create_index("order")
            logger.info("Database indexes checked/initialized.")
        except Exception as e:
            logger.error(f"Index initialization failed: {e}")

# This creates a default instance for the main Flask application to use
db = DataAccessLayer()