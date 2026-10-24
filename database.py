"""Small DB-API bridge for the CRM's existing parameterized SQLite-style queries.

PostgreSQL is selected only by DATABASE_URL; a configured but unavailable database
never falls back to an empty SQLite file. Business schemas and JSON stay intact.
"""
import re
import sqlite3
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus

WRITE_LOCK = 478502196001
TOKENS = re.compile(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*.*?\*/)|(\?)", re.S)


def postgres_sql(statement, bound=False):
    if bound: statement = statement.replace('%', '%%')
    statement = TOKENS.sub(lambda match: match[1] if match[1] is not None else '%s', statement)
    return statement


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Cursor:
    def __init__(self, cursor): self.cursor = cursor
    @property
    def rowcount(self): return self.cursor.rowcount
    def fetchone(self):
        value = self.cursor.fetchone()
        return Row(value) if value is not None else None
    def fetchall(self): return [Row(value) for value in self.cursor.fetchall()]
    def __iter__(self):
        for row in self.cursor: yield Row(row)


class PostgresConnection:
    backend = 'postgresql'
    def __init__(self, connection): self.connection = connection

    def execute(self, statement, parameters=None):
        try:
            command = statement.strip().rstrip(';').upper()
            if command == 'BEGIN IMMEDIATE':
                if self.connection.info.transaction_status == TransactionStatus.IDLE:
                    self.connection.execute('BEGIN')
                return Cursor(self.connection.execute('SELECT pg_advisory_xact_lock(%s)', (WRITE_LOCK,)))
            if command == 'BEGIN':
                if self.connection.info.transaction_status != TransactionStatus.IDLE:
                    raise sqlite3.ProgrammingError('A transaction is already active.')
                return Cursor(self.connection.execute('BEGIN ISOLATION LEVEL REPEATABLE READ'))
            return Cursor(self.connection.execute(postgres_sql(statement, parameters is not None), parameters))
        except psycopg.Error:
            raise sqlite3.DatabaseError('PostgreSQL could not complete the database operation. Check connectivity and server logs.') from None

    def executemany(self, statement, parameters):
        try:
            cursor = self.connection.cursor()
            cursor.executemany(postgres_sql(statement, True), parameters)
            return Cursor(cursor)
        except psycopg.Error:
            raise sqlite3.DatabaseError('PostgreSQL could not save this batch. No partial transaction was committed.') from None

    def executescript(self, script):
        # Only the application's fixed schema DDL uses this method, never user SQL.
        script = script.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY')
        script = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', script)
        script = re.sub(r'\bBLOB\b', 'BYTEA', script)
        for statement in script.split(';'):
            if statement.strip(): self.execute(statement)


@contextmanager
def connect(sqlite_path, database_url=''):
    if not database_url:
        connection = sqlite3.connect(sqlite_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            with connection: yield connection
        finally: connection.close()
        return
    if not database_url.startswith(('postgresql://', 'postgres://')):
        raise sqlite3.DatabaseError('DATABASE_URL must be a PostgreSQL connection URL.')
    try:
        connection = psycopg.connect(database_url, connect_timeout=15, row_factory=dict_row,
            application_name='hospkart-crm', options='-c statement_timeout=60000 -c lock_timeout=15000')
    except psycopg.Error:
        raise sqlite3.DatabaseError('The configured PostgreSQL database could not be reached. Existing data was not changed; SQLite fallback is disabled.') from None
    try:
        with connection: yield PostgresConnection(connection)
    except psycopg.Error:
        raise sqlite3.DatabaseError('PostgreSQL could not commit the transaction. Saved data was retained.') from None

