# utils/db_connection.py
from pymongo import MongoClient
from neo4j import GraphDatabase
from django.conf import settings

# --- KẾT NỐI MONGODB ---
def get_mongo_db():
    client = MongoClient(settings.MONGO_URI)
    return client[settings.MONGO_DB_NAME]

# --- KẾT NỐI NEO4J ---
class Neo4jConnection:
    def __init__(self):
        self.driver = GraphDatabase.driver(settings.NEO4J_URI, auth=settings.NEO4J_AUTH)

    def close(self):
        self.driver.close()

    def get_session(self):
        return self.driver.session()

# Hàm tiện ích để lấy session nhanh
def get_neo4j_session():
    conn = Neo4jConnection()
    return conn.get_session()