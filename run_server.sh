#!/bin/bash

# Script to run ADK agents via the built-in web server
# This is more stable than custom FastAPI integration

echo "Starting ADK web server on port 8010..."
echo "Access at: http://localhost:8010"
echo ""

# Use ADK's built-in web command which is more stable
adk web --host 0.0.0.0 --port 8010
