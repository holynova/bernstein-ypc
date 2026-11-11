#!/Users/sym/.local/share/uv/tools/notebooklm-mcp-cli/bin/python3
"""Run nlm CLI with automatic mutation retries disabled.

Prevents duplicate remote slide/source creation when network RPCs time out.
"""
import os
import sys

os.environ["NOTEBOOKLM_RATE_LIMIT_MAX_RETRIES"] = "0"
import notebooklm_tools.core.base as base

base.DEFAULT_MAX_RETRIES = 0
from notebooklm_tools.cli.main import cli_main

if __name__ == "__main__":
    sys.exit(cli_main())
