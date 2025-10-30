# Reflex + Google ADK FastAPI Backend Integration Plan

## Overview

This document outlines how to integrate the existing Google ADK FastAPI backend with a Reflex frontend application. Reflex allows building full-stack Python web apps with the backend being a FastAPI/Starlette application.

## Architecture

```
┌─────────────────────────────────────────────┐
│         Reflex Frontend (Python)            │
│  ┌───────────────────────────────────────┐  │
│  │  UI Components (rx.components)         │  │
│  │  - Chat interface                      │  │
│  │  - Session management                  │  │
│  │  - Artifact viewer                     │  │
│  └───────────────────────────────────────┘  │
│                    ↓                          │
│  ┌───────────────────────────────────────┐  │
│  │  Reflex State Management               │  │
│  │  - AgentState                          │  │
│  │  - SessionState                        │  │
│  │  - ArtifactState                       │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                    ↓ HTTP/WebSocket
┌─────────────────────────────────────────────┐
│   Google ADK FastAPI Backend (server.py)   │
│  ┌───────────────────────────────────────┐  │
│  │  ADK Web Server Endpoints              │  │
│  │  - /apps/{app}/users/{user}/sessions   │  │
│  │  - /apps/{app}/...​/artifacts          │  │
│  │  - /run, /run_sse                      │  │
│  └───────────────────────────────────────┘  │
│  ┌───────────────────────────────────────┐  │
│  │  ADK Services                          │  │
│  │  - Session Service                     │  │
│  │  - Artifact Service                    │  │
│  │  - Agent Loader                        │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│       Google ADK Multi-Agent System         │
│  - movie_pitch_agent (LoopAgent)           │
│  - screenwriter, researcher, critic        │
│  - Saves artifacts to session              │
└─────────────────────────────────────────────┘
```

## Integration Methods

### Option 1: API Transformer (Recommended)

Use Reflex's `api_transformer` to integrate the existing FastAPI app:

```python
# reflex_app.py
import reflex as rx
from server import app as fastapi_app

# Create Reflex app with ADK FastAPI backend
reflex_app = rx.App(api_transformer=fastapi_app)
```

**Pros:**
- Minimal changes to existing FastAPI backend
- Reflex and ADK share the same server process
- Single deployment unit
- Shared ASGI middleware and CORS

**Cons:**
- Tight coupling between frontend and backend
- Both must restart together

### Option 2: Separate Services (Microservices)

Run Reflex frontend and ADK backend as separate services:

```python
# reflex_app.py - Frontend only
import reflex as rx
import httpx

class AgentState(rx.State):
    async def send_message(self, message: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8010/apps/movie_pitch_agent/users/user/sessions/{session_id}",
                json={"message": {"role": "user", "parts": [{"text": message}]}}
            )
```

**Pros:**
- Independent scaling
- Can update frontend without touching backend
- Backend can serve multiple frontends

**Cons:**
- Need to manage CORS
- Two deployment units
- Extra HTTP overhead

## Recommended Approach: Option 1 (API Transformer)

This provides the best developer experience and simplest deployment.

## Implementation Steps

### Step 1: Install Reflex

```bash
cd /Users/cmcewing/Documents/forgelabs/projects/forgelabs/reflex-adk-test
uv add reflex
```

### Step 2: Create Reflex App Structure

```
reflex-adk-test/
├── server.py                 # Existing ADK FastAPI server
├── config.py                 # Existing config
├── movie_pitch_agent/        # Existing agent
├── reflex_app/               # NEW: Reflex frontend
│   ├── __init__.py
│   ├── reflex_app.py        # Main Reflex app
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── index.py         # Home page
│   │   ├── chat.py          # Chat interface
│   │   └── artifacts.py     # Artifact viewer
│   └── state/
│       ├── __init__.py
│       ├── agent_state.py   # Agent interaction state
│       ├── session_state.py # Session management
│       └── artifact_state.py # Artifact viewing
├── rxconfig.py              # NEW: Reflex configuration
└── assets/                  # NEW: Static assets
```

### Step 3: Create Reflex Configuration

```python
# rxconfig.py
import reflex as rx

config = rx.Config(
    app_name="reflex_app",
    api_url="http://localhost:8010",  # ADK backend URL
    port=3000,  # Reflex frontend port
    cors_allowed_origins=[
        "http://localhost:3000",
        "http://localhost:8010",
    ]
)
```

### Step 4: Integrate with Existing FastAPI Backend

```python
# reflex_app/reflex_app.py
import reflex as rx
from server import app as adk_fastapi_app
from reflex_app.pages import index, chat, artifacts

# Create Reflex app with ADK backend as transformer
app = rx.App(api_transformer=adk_fastapi_app)

# Add pages
app.add_page(index.page, route="/")
app.add_page(chat.page, route="/chat")
app.add_page(artifacts.page, route="/artifacts")
```

### Step 5: Create Agent State Management

```python
# reflex_app/state/agent_state.py
import reflex as rx
import httpx
from typing import List, Tuple

class AgentState(rx.State):
    """State for interacting with Google ADK agents."""

    # Session management
    session_id: str = ""
    app_name: str = "movie_pitch_agent"
    user_id: str = "user"

    # Chat
    messages: List[Tuple[str, str]] = []
    current_message: str = ""
    is_processing: bool = False

    async def create_session(self):
        """Create a new ADK session."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8010/apps/{self.app_name}/users/{self.user_id}/sessions",
                json={}
            )
            data = response.json()
            self.session_id = data["id"]

    async def send_message(self):
        """Send message to the agent."""
        if not self.current_message.strip():
            return

        if not self.session_id:
            await self.create_session()

        self.is_processing = True
        user_message = self.current_message
        self.messages.append((user_message, ""))
        self.current_message = ""
        yield

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://localhost:8010/apps/{self.app_name}/users/{self.user_id}/sessions/{self.session_id}",
                    json={
                        "message": {
                            "role": "user",
                            "parts": [{"text": user_message}]
                        }
                    },
                    timeout=120.0
                )

                # Handle streaming response
                agent_response = ""
                async for chunk in response.aiter_text():
                    agent_response += chunk
                    self.messages[-1] = (user_message, agent_response)
                    yield

        finally:
            self.is_processing = False
```

### Step 6: Create Artifact State

```python
# reflex_app/state/artifact_state.py
import reflex as rx
import httpx
from typing import List, Dict

class ArtifactState(rx.State):
    """State for managing artifacts."""

    session_id: str = ""
    app_name: str = "movie_pitch_agent"
    user_id: str = "user"

    artifacts: List[Dict] = []
    selected_artifact: str = ""
    artifact_content: str = ""

    async def load_artifacts(self):
        """Load artifacts for the current session."""
        if not self.session_id:
            return

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8010/apps/{self.app_name}/users/{self.user_id}/sessions/{self.session_id}/artifacts"
            )
            data = response.json()
            self.artifacts = data.get("artifacts", [])

    async def download_artifact(self, filename: str):
        """Download and display artifact content."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:8010/apps/{self.app_name}/users/{self.user_id}/sessions/{self.session_id}/artifacts/{filename}"
            )
            self.selected_artifact = filename
            self.artifact_content = response.text
```

### Step 7: Create Chat Interface

```python
# reflex_app/pages/chat.py
import reflex as rx
from reflex_app.state.agent_state import AgentState

def message_bubble(message: Tuple[str, str]) -> rx.Component:
    """Render a message bubble."""
    user_msg, agent_msg = message

    return rx.vstack(
        # User message
        rx.hstack(
            rx.box(
                rx.text(user_msg, color="white"),
                background="blue.500",
                padding="0.75em",
                border_radius="lg",
            ),
            justify="end",
        ),
        # Agent response
        rx.cond(
            agent_msg != "",
            rx.hstack(
                rx.box(
                    rx.markdown(agent_msg),
                    background="gray.100",
                    padding="0.75em",
                    border_radius="lg",
                ),
                justify="start",
            ),
        ),
        width="100%",
        spacing="2",
    )

def chat_interface() -> rx.Component:
    """Main chat interface."""
    return rx.vstack(
        rx.heading("Movie Pitch Agent", size="8"),

        # Chat history
        rx.box(
            rx.foreach(
                AgentState.messages,
                message_bubble
            ),
            height="60vh",
            overflow_y="auto",
            width="100%",
            padding="4",
        ),

        # Input area
        rx.hstack(
            rx.input(
                placeholder="Ask the agent to create a movie pitch...",
                value=AgentState.current_message,
                on_change=AgentState.set_current_message,
                width="100%",
            ),
            rx.button(
                "Send",
                on_click=AgentState.send_message,
                loading=AgentState.is_processing,
            ),
            width="100%",
        ),

        width="800px",
        spacing="4",
    )

def page() -> rx.Component:
    return rx.center(
        chat_interface(),
        padding="4",
    )
```

### Step 8: Create Artifact Viewer

```python
# reflex_app/pages/artifacts.py
import reflex as rx
from reflex_app.state.artifact_state import ArtifactState

def artifact_list() -> rx.Component:
    """Display list of artifacts."""
    return rx.vstack(
        rx.heading("Movie Pitch Artifacts", size="6"),
        rx.button(
            "Refresh",
            on_click=ArtifactState.load_artifacts,
        ),
        rx.foreach(
            ArtifactState.artifacts,
            lambda artifact: rx.button(
                artifact["filename"],
                on_click=lambda: ArtifactState.download_artifact(artifact["filename"]),
                width="100%",
            ),
        ),
        spacing="2",
        width="300px",
    )

def artifact_viewer() -> rx.Component:
    """Display artifact content."""
    return rx.vstack(
        rx.heading(ArtifactState.selected_artifact, size="6"),
        rx.box(
            rx.markdown(ArtifactState.artifact_content),
            background="gray.50",
            padding="4",
            border_radius="md",
            height="70vh",
            overflow_y="auto",
        ),
        spacing="4",
        width="100%",
    )

def page() -> rx.Component:
    return rx.center(
        rx.hstack(
            artifact_list(),
            artifact_viewer(),
            spacing="4",
            align="start",
        ),
        padding="4",
    )
```

## Deployment

### Development

```bash
# Start backend (ADK + Reflex combined)
uv run reflex run

# This will:
# - Start FastAPI backend on port 8010
# - Start Reflex frontend on port 3000
# - Hot reload on code changes
```

### Production

```bash
# Export for deployment
uv run reflex export

# Deploy to Cloud Run
gcloud run deploy reflex-adk-app \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

## Key Considerations

### 1. CORS Configuration

Since Reflex frontend (port 3000) talks to ADK backend (port 8010), ensure CORS is configured:

```python
# In server.py
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Reflex dev server
    "http://localhost:8010",  # ADK backend
]
```

### 2. Session Management

- Reflex maintains its own WebSocket state
- ADK uses HTTP sessions
- Need to sync session IDs between both systems

### 3. Real-time Updates

Use Reflex's streaming with `yield` for real-time agent responses:

```python
async def send_message(self):
    # ... send message ...
    async for chunk in response.aiter_text():
        self.messages[-1] = (user_msg, agent_response)
        yield  # Update UI in real-time
```

### 4. Authentication

Add auth middleware to both Reflex and ADK:

```python
# Add to api_transformer
def add_auth_middleware(app):
    @app.middleware("http")
    async def auth_middleware(request, call_next):
        # Verify JWT or session
        response = await call_next(request)
        return response
    return app

app = rx.App(api_transformer=[fastapi_app, add_auth_middleware])
```

## Benefits of This Architecture

1. **Single Codebase**: All Python, no JavaScript
2. **Type Safety**: Full type hints across frontend and backend
3. **Real-time**: WebSocket support for live updates
4. **Production Ready**: Built on FastAPI/Starlette
5. **Cloud Native**: Works with Cloud Run, GKE, etc.
6. **Developer Experience**: Hot reload, single command to run

## Next Steps

1. Install Reflex: `uv add reflex`
2. Create `reflex_app/` directory structure
3. Implement `AgentState` for chat interface
4. Build chat UI with real-time streaming
5. Add artifact viewer
6. Test integration locally
7. Deploy to Cloud Run

## Example Full Integration

```python
# main.py - Complete integration
import reflex as rx
from server import app as adk_app
from reflex_app.pages import index, chat, artifacts

# Integrate ADK FastAPI backend
app = rx.App(
    api_transformer=adk_app,
    theme=rx.theme(accent_color="blue"),
)

# Add pages
app.add_page(index.page, route="/", title="Home")
app.add_page(chat.page, route="/chat", title="Movie Pitch Agent")
app.add_page(artifacts.page, route="/artifacts", title="Artifacts")

# Run with: reflex run
```

This creates a complete full-stack Python application with Google ADK agents and a modern Reflex UI! 🚀
