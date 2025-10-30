"""
Configuration for Google ADK Multi-Agent System.

This module provides configuration settings that can be overridden by environment variables.
Uses Google Application Default Credentials (ADC) for authentication.
"""

import os

# ==============================================================================
# AI Model Configuration
# ==============================================================================

# Gemini model to use (can be overridden by MODEL env var)
MODEL = os.getenv("MODEL", "gemini-2.5-flash")

# ==============================================================================
# Server Configuration
# ==============================================================================

# Server host and port
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8010"))

# Environment: development or production
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ==============================================================================
# Database Configuration
# ==============================================================================

# Session database URL (SQLite by default)
SESSION_DB_URL = os.getenv("SESSION_DB_URL", "sqlite:///./sessions.db")

# ==============================================================================
# CORS Configuration
# ==============================================================================

# Allowed origins for CORS (comma-separated)
ALLOWED_ORIGINS_STR = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_STR.split(",")]

# ==============================================================================
# Google Cloud Configuration
# ==============================================================================

# Use Vertex AI instead of Google AI Studio (required for ADC authentication)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")

# Google Cloud project and region (optional - uses gcloud config by default)
# Only set these if you want to override the gcloud defaults
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")  # None = use gcloud config
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Enable Google Cloud Logging (optional)
ENABLE_CLOUD_LOGGING = os.getenv("ENABLE_CLOUD_LOGGING", "").lower() == "true"
