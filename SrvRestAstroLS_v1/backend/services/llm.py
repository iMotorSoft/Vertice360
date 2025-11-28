"""
Stub for a centralized LLM wrapper.
Later iterations will inject tenant-aware credentials and usage logging.
"""


def call_llm(prompt: str, tenant_id: str | None = None, purpose: str | None = None) -> str:
    """
    Stub for a centralized LLM call.
    - In this initial version, it echoes the prompt.
    - Later it will read API keys from environment variables (set in shell) and log token usage per tenant.
    """
    return f"LLM stub response for prompt: {prompt}"
