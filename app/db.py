import psycopg2
from psycopg2 import pool

# Configuración de la conexión
DB_CONFIG = {
    "host": "172.31.0.19",
    "database": "bd_app_pm",
    "user": "admin",
    "password": "87654321",
    'port': 5432
}

# Pool de conexiones
connection_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **DB_CONFIG)

def get_connection():
    return connection_pool.getconn()

def return_connection(conn):
    connection_pool.putconn(conn)