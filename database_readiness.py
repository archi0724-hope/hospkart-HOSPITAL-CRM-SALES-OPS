"""Retry database initialization without opening an empty fallback database."""
import logging
import sqlite3
from threading import Lock
from time import monotonic


class DatabaseReadiness:
    def __init__(self, initialize, *, defer_errors=False, retry_seconds=60):
        self.initialize = initialize
        self.defer_errors = defer_errors
        self.retry_seconds = retry_seconds
        self.ready = False
        self.next_attempt = 0
        self.lock = Lock()

    def ensure(self):
        if self.ready:
            return True
        if monotonic() < self.next_attempt or not self.lock.acquire(blocking=False):
            return False
        try:
            if self.ready:
                return True
            if monotonic() < self.next_attempt:
                return False
            try:
                self.initialize()
            except sqlite3.DatabaseError:
                if not self.defer_errors:
                    raise
                self.next_attempt = monotonic() + self.retry_seconds
                logging.getLogger(__name__).warning('Database initialization unavailable; serving maintenance responses and retrying later.')
                return False
            self.ready = True
            return True
        finally:
            self.lock.release()
