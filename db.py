import os
import mysql.connector
from mysql.connector import Error

def connect_races():
    conn = None
    host = os.getenv("RACES_DB_HOST"),
    port = int(os.getenv("RACES_DB_PORT"))
    user = os.getenv("RACES_DB_USER")
    db_name = os.getenv("RACES_DB_NAME")
    password = os.getenv("RACES_DB_PASS")
    
    try:
        conn = mysql.connector.connect(host=host,
                                       database=db_name,
                                       port=port,
                                       user=user,
                                       password='SecurePass1!')
        if conn.is_connected():
            print('Connected to MySQL database')
 
    except Error as e:
        print(e)

    return conn

def connect_rankings():
    conn = None
    host = os.getenv("RANKINGS_DB_HOST"),
    port = int(os.getenv("RANKINGS_DB_PORT"))
    user = os.getenv("RANKINGS_DB_USER")
    db_name = os.getenv("RANKINGS_DB_NAME")
    password = os.getenv("RANKINGS_DB_PASS")
    try:
        conn = mysql.connector.connect(host=host,
                                       database=db_name,
                                       port=port,
                                       user=user,
                                       password=password)
        if conn.is_connected():
            print('Connected to MySQL database')
 
    except Error as e:
        print(e)

    return conn
