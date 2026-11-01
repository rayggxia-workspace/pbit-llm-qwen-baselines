"""Canonical full-model TLM entry; implementation remains unified_v6."""
import sys

if '--shared-memory' in sys.argv[1:]:
    sys.argv.remove('--shared-memory')
    from .unified_v6.shared_decode import main
else:
    from .unified_v6.run import main
main()
