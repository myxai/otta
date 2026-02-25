"""myxai_desk.core.capabilities — Governance wrappers + standalone fallback.

Two execution paths:

1. **Agent loop** (primary):
   nanobot's tools.execute() does the work.
   ``governance.post_execution_audit`` / ``post_execution_undo`` run **after**
   each nanobot tool call to record audit entries and register undo actions.

2. **Prompt App runtime** (standalone fallback):
   When a Prompt App runs outside the nanobot Agent loop, the standalone
   capability classes (FS, Proc, SearchCapability, …) handle execution
   with their own built-in audit and undo hooks.

Modules
-------
- governance : post-execution hooks called from the Agent loop in app.py
- fs         : standalone file-system operations (Prompt App fallback)
- proc       : standalone subprocess execution (Prompt App fallback)
- search     : QuotaManager (always active) + standalone search (fallback)
- net        : standalone HTTP capability (Prompt App fallback)
- mcp        : MCP bridge wrapper
- notify     : frontend notification push
- cron       : scheduled trigger manager
- profile    : user profile data access
"""
