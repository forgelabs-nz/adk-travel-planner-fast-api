"""FastAPI server for Google ADK agents.

This server exposes ADK agents as HTTP endpoints using FastAPI and uvicorn.
Production-ready approach that manually initializes ADK services.
"""

import os
import sys
import logging
from pathlib import Path

# Import configuration
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional: Setup Google Cloud Logging if enabled
if config.ENABLE_CLOUD_LOGGING:
    try:
        import google.cloud.logging as cloud_logging
        project_id = config.GOOGLE_CLOUD_PROJECT
        if project_id:
            client = cloud_logging.Client(project=project_id)
            client.setup_logging()
            logger.info(f"✓ Google Cloud Logging enabled for project: {project_id}")
        else:
            logger.warning("ENABLE_CLOUD_LOGGING is true but GOOGLE_CLOUD_PROJECT is not set")
    except Exception as e:
        logger.warning(f"Failed to setup Cloud Logging: {e}")

# Import ADK components
try:
    from google.adk.cli.adk_web_server import AdkWebServer
    from google.adk.sessions.database_session_service import DatabaseSessionService
    from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
    from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
    from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
    from google.adk.evaluation.local_eval_sets_manager import LocalEvalSetsManager
    from google.adk.evaluation.local_eval_set_results_manager import LocalEvalSetResultsManager
    from google.adk.cli.utils.agent_loader import AgentLoader
    import google.adk.cli.browser
except ImportError as e:
    print(f"Error: Failed to import Google ADK. Have you run 'uv sync'?")
    print(f"Details: {e}")
    sys.exit(1)

# ==============================================================================
# Configuration
# ==============================================================================

# Agent directory (current directory contains agent subdirectories)
AGENT_DIR = Path(__file__).parent

# Use configuration from config.py
SESSION_SERVICE_URI = config.SESSION_DB_URL
ALLOWED_ORIGINS = config.ALLOWED_ORIGINS
ENVIRONMENT = config.ENVIRONMENT

# ==============================================================================
# Initialize ADK Services
# ==============================================================================

logger.info(f"Initializing ADK services for agents in: {AGENT_DIR}")

# Create services (in production, you might use GCS for artifacts)
session_service = DatabaseSessionService(db_url=SESSION_SERVICE_URI)
artifact_service = InMemoryArtifactService()
memory_service = InMemoryMemoryService()
credential_service = InMemoryCredentialService()

# Create agent loader
agent_loader = AgentLoader(str(AGENT_DIR))
eval_sets_manager = LocalEvalSetsManager(agents_dir=str(AGENT_DIR))
eval_set_results_manager = LocalEvalSetResultsManager(agents_dir=str(AGENT_DIR))

# Get ADK web assets directory for dev-ui
ADK_WEB_ASSETS_DIR = Path(google.adk.cli.browser.__path__[0])

# Create ADK web server with explicit service configuration
adk_web_server = AdkWebServer(
    agent_loader=agent_loader,
    session_service=session_service,
    artifact_service=artifact_service,
    memory_service=memory_service,
    credential_service=credential_service,
    eval_sets_manager=eval_sets_manager,
    eval_set_results_manager=eval_set_results_manager,
    agents_dir=str(AGENT_DIR),
)

# Create FastAPI app from the ADK web server
app = adk_web_server.get_fast_api_app(
    allow_origins=ALLOWED_ORIGINS,
    web_assets_dir=str(ADK_WEB_ASSETS_DIR),
)

# Store services in app state for custom endpoints
app.state.artifact_service = artifact_service
app.state.session_service = session_service

logger.info("✓ ADK services initialized successfully")

# ==============================================================================
# Fix OpenAPI Schema Generation
# ==============================================================================

def custom_openapi():
    """
    Generate OpenAPI schema while filtering out routes with MCP ClientSession types.

    This works around the Pydantic schema generation error for MCP types
    by excluding problematic ADK internal routes from schema generation.
    """
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi
    from fastapi.routing import APIRoute

    # First, let's log what routes we have for debugging
    logger.info("Analyzing routes for OpenAPI schema generation...")
    all_route_paths = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            all_route_paths.append(route.path)
    logger.info(f"Total API routes found: {len(all_route_paths)}")
    logger.debug(f"Routes: {all_route_paths}")

    # Filter routes to exclude those that cause MCP ClientSession errors
    # Keep our custom routes and core ADK routes
    safe_routes = []
    skipped_routes = []

    for route in app.routes:
        if isinstance(route, APIRoute):
            # Exclude routes that have MCP-related paths or might have ClientSession types
            # These are internal ADK routes that cause Pydantic schema generation errors
            skip_patterns = [
                '/tools/mcp',  # MCP tool routes that have ClientSession types
                '/eval-sets',  # Eval set routes with MCP ClientSession types
                '/eval_sets',  # Alternative eval set routes
                '/eval-results',  # Eval result routes with GenericAlias types
                '/eval_results',  # Alternative eval result routes
                '/eval-cases',  # Eval case routes
                '/eval_cases',  # Alternative eval case routes
            ]

            should_skip = any(pattern in route.path for pattern in skip_patterns)

            if should_skip:
                skipped_routes.append(route.path)
            else:
                safe_routes.append(route)
        else:
            # Include non-API routes (like static file routes)
            safe_routes.append(route)

    logger.info(f"Including {len(safe_routes)} routes in schema")
    logger.info(f"Skipping {len(skipped_routes)} routes: {skipped_routes}")

    try:
        openapi_schema = get_openapi(
            title="Google ADK Multi-Agent System API",
            version="0.1.0",
            description="""
            Production-ready API for Google ADK agents with FastAPI and uvicorn.

            ## Features
            - Multi-agent workflows (Sequential, Parallel, Loop patterns)
            - Session management with persistence
            - Artifact storage
            - Real-time agent interaction

            ## Available Agents
            - **movie_pitch_agent**: Movie pitch generation with iterative refinement

            Note: Some internal MCP tool management routes are excluded from this schema.
            """,
            routes=safe_routes,
            servers=[
                {"url": "/", "description": "Current server"}
            ]
        )

        # Add custom metadata
        openapi_schema["info"]["x-logo"] = {
            "url": "https://www.gstatic.com/devrel-devsite/prod/v2f1fc4f4f8c6f3b3f3f3f3f3f3f3f3f3/cloud/images/favicons/onecloud/super_cloud.png"
        }

        logger.info("✓ OpenAPI schema generated successfully")

    except Exception as e:
        import traceback
        logger.error(f"OpenAPI schema generation failed: {e}")
        logger.debug(f"Full traceback: {traceback.format_exc()}")

        # Return minimal working schema
        openapi_schema = {
            "openapi": "3.0.2",
            "info": {
                "title": "Google ADK Multi-Agent System API",
                "version": "0.1.0",
                "description": "API schema generation partially limited due to MCP type constraints"
            },
            "paths": {
                "/health": {
                    "get": {
                        "summary": "Health Check",
                        "operationId": "health_check",
                        "responses": {
                            "200": {
                                "description": "Successful Response",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "status": {"type": "string"},
                                                "environment": {"type": "string"},
                                                "version": {"type": "string"},
                                                "agents": {
                                                    "type": "array",
                                                    "items": {"type": "string"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "tags": ["monitoring"]
                    }
                },
                "/info": {
                    "get": {
                        "summary": "Service Information",
                        "operationId": "get_info",
                        "responses": {
                            "200": {
                                "description": "Successful Response",
                                "content": {
                                    "application/json": {
                                        "schema": {"type": "object"}
                                    }
                                }
                            }
                        },
                        "tags": ["information"]
                    }
                }
            }
        }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Override the default OpenAPI schema generation
app.openapi = custom_openapi

logger.info("✓ Custom OpenAPI schema handler installed")

# ==============================================================================
# Custom Endpoints
# ==============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "environment": ENVIRONMENT,
        "version": "0.1.0",
        "agents": ["movie_pitch_agent"]
    }

@app.get("/info")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Google ADK Multi-Agent System",
        "version": "0.1.0",
        "environment": ENVIRONMENT,
        "agents": {
            "movie_pitch_agent": "Movie pitch generation with iterative refinement using multi-agent workflows"
        },
        "endpoints": {
            "health": "/health",
            "info": "/info",
            "web_ui": "/",
            "docs": "/docs (may have OpenAPI schema limitations)",
        }
    }

# ==============================================================================
# Application Entry Point
# ==============================================================================

if __name__ == "__main__":
    import uvicorn

    # Get configuration
    port = config.PORT
    host = config.HOST
    reload = config.ENVIRONMENT == "development"

    # Print startup banner
    print("\n" + "=" * 70)
    print("  Google ADK Multi-Agent System")
    print("=" * 70)
    print(f"  Environment:       {ENVIRONMENT}")
    print(f"  Server:            http://{host}:{port}")
    print(f"  Web UI:            http://{host}:{port}")
    print(f"  Health Check:      http://{host}:{port}/health")
    print(f"  Hot Reload:        {'Enabled' if reload else 'Disabled'}")
    print("=" * 70 + "\n")

    # Start server
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload
    )
