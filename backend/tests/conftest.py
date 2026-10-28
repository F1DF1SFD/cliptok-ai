import os
import tempfile

# Isolate test data before any application module reads the config.
os.environ.setdefault("CLIPTOK_DATA_DIR", tempfile.mkdtemp(prefix="cliptok-test-"))
os.environ.setdefault("CLIPTOK_WHISPER_MODEL", "tiny")
