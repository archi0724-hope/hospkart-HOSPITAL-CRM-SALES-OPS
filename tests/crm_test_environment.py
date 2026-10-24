"""Keep tests off a developer's configured production PostgreSQL database."""
import os

os.environ['DATABASE_URL'] = ''
os.environ['SCHEDULER_ENABLED'] = 'false'

import app  # noqa: E402
