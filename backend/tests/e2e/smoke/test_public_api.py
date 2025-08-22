#!/usr/bin/env python
"""
Public API Test Script

Entry point for the modularized public API test suite.
Tests Airweave API across different environments:
- local: Starts services via start.sh, uses localhost:8001
- dev: Uses api.dev-airweave.com
- prod: Uses api.airweave.ai

Usage:
    # Set environment variables:
    export STRIPE_API_KEY=sk_test_...
    export OPENAI_API_KEY=...         # Optional for local
    export AIRWEAVE_API_KEY=...       # Required for dev/prod

    # Run tests:
    python test_public_api.py          # Defaults to local
    python test_public_api.py --env local
    python test_public_api.py --env dev
    python test_public_api.py --env prod
"""

import sys
import os

# Add the current directory to Python path to enable imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import and run the modularized test runner
from public_api_tests.runner import main

if __name__ == "__main__":
    main()
