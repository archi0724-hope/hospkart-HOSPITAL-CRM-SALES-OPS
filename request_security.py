"""Origin checks for direct HTTP and HTTPS terminated by a reverse proxy."""
from urllib.parse import urlsplit


def crm_request_origin_allowed(request):
    if request.headers.get('Sec-Fetch-Site', '').lower() == 'cross-site':
        return False
    raw = request.headers.get('Origin')
    if raw is None:
        return True  # CLI/internal clients still need each route's JSON/header checks.
    try:
        origin, target = urlsplit(raw), urlsplit(request.host_url)
        if (origin.scheme not in ('http', 'https') or not origin.hostname or
                origin.username is not None or origin.password is not None or
                origin.path not in ('', '/') or origin.query or origin.fragment):
            return False
        if origin.hostname != target.hostname:
            return False
        if origin.scheme != target.scheme:
            # TLS terminators commonly preserve Host but forward using HTTP.
            # Permit that one direction for the SAME public host and port.
            # Do not use X-Forwarded-Host from an untrusted client.
            if not (origin.scheme == 'https' and target.scheme == 'http'):
                return False
        default_port = 443 if origin.scheme == 'https' else 80
        return (origin.port or default_port) == (target.port or default_port)
    except (ValueError, UnicodeError):
        return False
