"""Serve the Flask app on Windows or Linux with one scheduler-owning process."""
import os

from waitress import serve
from app import app


def server_options():
    options={'host':os.getenv('HOST','0.0.0.0'),'port':int(os.getenv('PORT','5000')),'threads':4}
    proxy=os.getenv('TRUSTED_PROXY','').strip()
    if proxy:
        options.update(trusted_proxy=proxy,trusted_proxy_count=int(os.getenv('TRUSTED_PROXY_COUNT','1')),trusted_proxy_headers={'x-forwarded-proto','x-forwarded-host','x-forwarded-port'})
    return options


if __name__ == '__main__':
    serve(app,**server_options())
