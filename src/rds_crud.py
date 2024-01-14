from abc import ABC, abstractmethod
from uuid import UUID
from typing import List, Tuple
import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
import json
import traceback


class RelationalDB(ABC):
    """
    Schema: id:int (PK) | wiki_id:int | category: str | wiki_url:str | super_categories: List[str] | sub_categories:List[str] | sub_articles: List[str]
    """

    @abstractmethod
    def _connect(self):
        pass

    @abstractmethod
    def add_record(self):
        pass

    @abstractmethod
    def batch_upsert(self, records: List[Tuple]):
        pass


class VectorTable(RelationalDB):
    """
    Extension of abstract base class specifically for pgvetor on aws rds

    """
    def __init__(self, dbname, user, password, host, port):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None
        self._connect()

    def _connect(self):
        try:
            self.conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
        except psycopg2.Error as e:
            print(f"Unable to connect to the database: {e}")

    def add_record(self, id, article_id, title, vector, encoding, metadata):
        try:
            with self.conn.cursor() as cur:
                cur.execute("INSERT INTO vectors (id, article_id, title, vector, encoding, metadata)"
                            "VALUES (%s, %s, %s, %s, %s, %s)", (id, article_id, title, vector, encoding, metadata))
                self.conn.commit()
        except psycopg2.Error as e:
            print(f"Failed to add record to vectors table: {e}")
            traceback.print_exc()

    def batch_upsert(self, records: List[Tuple]):
        query = """
        INSERT INTO vectors (id, article_id, title, vector, encoding, metadata) 
        VALUES %s
        ON CONFLICT (id) DO UPDATE 
        SET article_id = EXCLUDED.article_id, 
            title = EXCLUDED.title, 
            vector = EXCLUDED.vector, 
            encoding = EXCLUDED.encoding, 
            metadata = EXCLUDED.metadata;
        """
        try:
            with self.conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    query,
                    records,
                    template="(%s, %s, %s, %s, %s, %s)",
                    page_size=100
                )
                self.conn.commit()
        except psycopg2.Error as e:
            print(f"Failed to batch upsert records to vectors table: {e}")
            traceback.print_exc()


class ArticleTable:
    def __init__(self, dbname, user, password, host, port):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None
        self._connect()

    def _connect(self):
        try:
            self.conn = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            print(f'Connected to the database {self.dbname} successfully!')
        except psycopg2.Error as e:
            print(f"Unable to connect to the database: {e}")
            traceback.print_exc()

    def add_record(self, id, title, text, raw_text):
        try:
            with self.conn.cursor() as cur:
                cur.execute("INSERT INTO articles (id, title, text, raw_text)"
                            "VALUES (%s, %s, %s, %s)", (id, title, text, raw_text))
                self.conn.commit()
        except psycopg2.Error as e:
            print(f"Failed to add record to articles table: {e}")
            traceback.print_exc()

    def batch_upsert(self, records: List[Tuple]):
        query = """
        INSERT INTO articles (id, title, text) 
        VALUES %s
        ON CONFLICT (id) DO UPDATE 
        SET 
            title = EXCLUDED.title, 
            text = EXCLUDED.text
        """
        try:
            with self.conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    query,
                    records,
                    template="(%s, %s, %s)",
                    page_size=100
                )
                self.conn.commit()
        except psycopg2.Error as e:
            print(f"Failed to batch upsert records to articles table: {e}")
            traceback.print_exc()

    def get_all_data_pd(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM articles")
            columns = [desc[0] for desc in cur.description]
            print(columns)
            data = [dict(zip(columns, row)) for row in cur.fetchall()]
        return pd.DataFrame(data)

    def get_all_data_json(self):
        df = self.get_all_data_pd()
        json_data = []
        for _, row in df.iterrows():
            text = row['text']
            labels = json.loads(row['label']) if isinstance(row['label'], str) else row['label']
            json_obj = {
                "text": text,
                "label": labels
            }
            json_data.append(json_obj)

        return json_data

    def close_connection(self):
        if self.conn is not None:
            self.conn.close()
