"""Loopback-only source mirror for one CPU allocation; parent owns lifecycle."""
import functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import sys

root, port_file = [Path(x).resolve() for x in sys.argv[1:]]
approved = Path('/home/Weican_Chen/projects/tlm-cycle-issue116-20261023')
assert root.is_relative_to(approved) and port_file.is_relative_to(approved)
server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(SimpleHTTPRequestHandler, directory=str(root)))
port_file.write_text(str(server.server_port) + '\n', encoding='utf-8')
server.serve_forever()
