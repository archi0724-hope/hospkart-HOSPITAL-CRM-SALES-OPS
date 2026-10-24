"""Adapter tests avoid external credentials and private production databases."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import database
import psycopg
from psycopg.pq import TransactionStatus


class DatabaseTests(unittest.TestCase):
    def test_bound_parameters_do_not_replace_quoted_question_marks(self):
        self.assertEqual(database.postgres_sql("SELECT '?' AS literal, ? AS value, '50%' AS percentage",True),
                         "SELECT '?' AS literal, %s AS value, '50%%' AS percentage")
        self.assertEqual(database.postgres_sql('SELECT "?column", ? -- ? comment\n',True),
                         'SELECT "?column", %s -- ? comment\n')

    def test_sqlite_commit_and_rollback_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'crm.db'
            with database.connect(path) as conn:conn.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)')
            with self.assertRaises(ValueError):
                with database.connect(path) as conn:
                    conn.execute('INSERT INTO sample VALUES (?,?)',(1,'Draft'));raise ValueError('rollback')
            with database.connect(path) as conn:self.assertEqual(conn.execute('SELECT count(*) FROM sample').fetchone()[0],0)

    def test_configured_postgres_failure_never_falls_back_or_leaks_credentials(self):
        with patch('database.psycopg.connect',side_effect=psycopg.OperationalError('password=very-private')),patch('database.sqlite3.connect') as sqlite:
            with self.assertRaises(sqlite3.DatabaseError) as caught:
                with database.connect('unused.db','postgresql://private.invalid/db'):pass
            self.assertNotIn('very-private',str(caught.exception));sqlite.assert_not_called()

    def test_global_write_lock_is_transaction_scoped_and_snapshot_begin_is_consistent(self):
        raw=MagicMock();raw.info.transaction_status=TransactionStatus.IDLE
        connection=database.PostgresConnection(raw)
        connection.execute('BEGIN IMMEDIATE')
        self.assertEqual(raw.execute.call_args_list[0].args[0],'BEGIN')
        self.assertIn('pg_advisory_xact_lock',raw.execute.call_args_list[-1].args[0])
        self.assertIn('SET LOCAL statement_timeout',raw.execute.call_args_list[1].args[0])
        raw.reset_mock();connection.execute('BEGIN')
        self.assertEqual(raw.execute.call_args_list[0].args[0],'BEGIN ISOLATION LEVEL REPEATABLE READ')
        self.assertIn('SET LOCAL lock_timeout',raw.execute.call_args_list[-1].args[0])

    def test_rows_support_mapping_and_legacy_numeric_indexing(self):
        row=database.Row({'total':7,'label':'saved'})
        self.assertEqual(row['total'],7);self.assertEqual(row[0],7);self.assertEqual(dict(row),{'total':7,'label':'saved'})

    def test_schema_translation_retains_high_precision_sync_timestamps(self):
        connection=database.PostgresConnection(MagicMock())
        with patch.object(connection,'execute') as execute:
            connection.executescript('CREATE TABLE sample (id INTEGER PRIMARY KEY AUTOINCREMENT, expires REAL);')
        sql=execute.call_args.args[0]
        self.assertIn('BIGSERIAL PRIMARY KEY',sql);self.assertIn('DOUBLE PRECISION',sql)
