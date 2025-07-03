import os
import logging
from pymongo import MongoClient, ReturnDocument, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure
from bson.objectid import ObjectId

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("database_sync")
logger.setLevel(logging.INFO)

class SyncDataAccessLayer:
    """A synchronous data access layer using pymongo for the Flask app."""
    def __init__(self, db_name: str = None):
        self.mongo_uri = os.getenv("MONGO_URI")
        self.db_name = db_name or os.getenv("MONGO_DB_NAME")
        if not self.mongo_uri or not self.db_name:
            raise ValueError("MONGO_URI and MONGO_DB_NAME must be set in .env file")

        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        logger.info(f"Sync Database connection established (db: {self.db_name})")
        self._initialize_indexes()

    def _convert_id(self, doc):
        """Converts a BSON ObjectId to a string."""
        if doc and '_id' in doc:
            doc['_id'] = str(doc['_id'])
        return doc
    
    def _query_with_str_id(self, query):
        """Converts a string '_id' in a query to an ObjectId."""
        if '_id' in query and isinstance(query['_id'], str):
            try:
                query['_id'] = ObjectId(query['_id'])
            except:
                pass 
        return query

    def find(self, collection: str, query: dict = {}, sort: list = None, limit: int = 0) -> list:
        query = self._query_with_str_id(query)
        cursor = self.db[collection].find(query).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        return [self._convert_id(doc) for doc in cursor]

    def get(self, collection: str, query: dict) -> dict | None:
        query = self._query_with_str_id(query)
        doc = self.db[collection].find_one(query)
        return self._convert_id(doc)

    def create(self, collection: str, data: dict) -> str:
        result = self.db[collection].insert_one(data)
        return str(result.inserted_id)

    def update(self, collection: str, query: dict, update_data: dict, upsert: bool = False) -> dict | None:
        query = self._query_with_str_id(query)
        result = self.db[collection].find_one_and_update(
            query,
            update_data,
            upsert=upsert,
            return_document=ReturnDocument.AFTER
        )
        return self._convert_id(result)

    def delete_many(self, collection: str, query: dict) -> int:
        query = self._query_with_str_id(query)
        result = self.db[collection].delete_many(query)
        return result.deleted_count

    def replace_collection(self, collection: str, data: list):
        self.db[collection].delete_many({})
        if data:
            self.db[collection].insert_many(data)

    def _initialize_indexes(self):
        """Creates indexes and safely ignores errors if they already exist."""
        try:
            self.db.users.create_index("username", unique=True)
            self.db.suggestions.create_index([("votes", DESCENDING)])
            self.db.suggestions.create_index("yt_id", unique=True, sparse=True)
            self.db.playlist.create_index("order")
            logger.info("Sync database indexes checked/initialized.")
        except OperationFailure as e:
            # Error codes 85 (IndexOptionsConflict) and 86 (IndexKeySpecsConflict) mean
            # an index with the same name but different options already exists.
            if e.code in [85, 86]:
                logger.warning(f"Could not create index, it likely already exists with different options: {e.details['errmsg']}")
            else:
                logger.error(f"Sync Index initialization failed: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during sync index initialization: {e}")

# Global instance for the Flask App to use
db = SyncDataAccessLayer()