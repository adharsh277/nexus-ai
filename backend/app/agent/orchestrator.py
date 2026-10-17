"""Agent orchestrator (PHASE 2 STUB).

TODO(phase-2):
- Build a prompt from the conversation history (app.models.Message rows).
- Call the local LLM (e.g. Ollama) with the tool schemas from app.agent.tools.
- Execute requested tool calls via app.services.* (always scoped to user_id),
  persist tool/assistant messages, and return the final assistant text.
- Hook in at app.services.chat.generate_reply.
"""
