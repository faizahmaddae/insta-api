"""
Production deployment configuration for Gunicorn.
Run with: gunicorn -c gunicorn.conf.py app.main:app
"""

import multiprocessing
import os

# Server socket
bind = os.getenv("BIND", "0.0.0.0:8000")
backlog = 2048

# Worker processes
# Rule of thumb: (2 × CPU cores) + 1
workers = int(os.getenv("WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 10000  # Restart workers after this many requests (prevents memory leaks)
max_requests_jitter = 1000  # Add randomness to prevent all workers restarting at once
timeout = 120  # Kill workers after 120s of no response
graceful_timeout = 30
keepalive = 5

# Process naming
proc_name = "instagram-api"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Logging
errorlog = "-"  # stderr
accesslog = "-"  # stdout
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# SSL (uncomment for HTTPS)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

# Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    pass

def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    pass

def worker_abort(worker):
    """Called when a worker receives SIGABRT (timeout)."""
    pass
