"""
SaveArtifactsPlugin for movie pitch agent.

This plugin automatically saves file-like content as artifacts with proper MIME type
and display_name metadata for the ADK WebUI.
"""

from __future__ import annotations

import copy
import logging
from typing import Optional

from google.genai import types
from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class SaveArtifactsPlugin(BasePlugin):
    """A plugin that saves artifacts with automatic metadata handling."""

    def __init__(self, name: str = 'save_artifacts_plugin'):
        """Initialize the plugin.

        Args:
            name: The name of the plugin instance.
        """
        super().__init__(name)

    async def on_agent_output_callback(
        self,
        *,
        invocation_context: InvocationContext,
        agent_output: types.Content,
    ) -> Optional[types.Content]:
        """Process agent output and save any artifacts with proper metadata.

        This callback examines the agent's output for inline_data parts (artifacts)
        and ensures they have proper MIME types and display names before saving.
        """
        if not invocation_context.artifact_service:
            logger.warning(
                'Artifact service is not set. SaveArtifactsPlugin will not be enabled.'
            )
            return None

        if not agent_output.parts:
            return None

        modified = False

        for i, part in enumerate(agent_output.parts):
            if part.inline_data is None:
                continue

            try:
                # Get display_name from the part, or generate one
                file_name = part.inline_data.display_name
                if not file_name:
                    file_name = f'artifact_{invocation_context.invocation_id}_{i}.txt'
                    logger.info(f'No display_name found, using generated filename: {file_name}')

                # Ensure MIME type is set
                if not part.inline_data.mime_type or part.inline_data.mime_type.strip() == '':
                    logger.warning(
                        f'Empty MIME type for {file_name}, using text/plain'
                    )
                    part.inline_data.mime_type = 'text/plain'

                # Save artifact with proper metadata
                await invocation_context.artifact_service.save_artifact(
                    app_name=invocation_context.app_name,
                    user_id=invocation_context.user_id,
                    session_id=invocation_context.session.id,
                    filename=file_name,
                    artifact=copy.copy(part),
                )

                modified = True
                logger.info(f'Successfully saved artifact: {file_name} ({part.inline_data.mime_type})')

            except Exception as e:
                logger.error(f'Failed to save artifact for part {i}: {e}')
                continue

        # Return None to indicate no modification to the output
        # (artifacts are saved but output remains unchanged)
        return None
