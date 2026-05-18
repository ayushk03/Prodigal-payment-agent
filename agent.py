"""
Payment Collection AI Agent
===========================
Exposes the required interface:
    agent = Agent()
    result = agent.next("Hi")  # → {"message": "..."}

Architecture:
- Agno (AgnoAgent) manages conversation history and session state.
- Google Gemini 2.5 Flash handles NLU and response generation.
- Three deterministic tools enforce all business rules.
- This thin Agent wrapper adapts Agno's interface to the required next() contract.
"""
import uuid
import os

from agno.agent import Agent as AgnoAgent
from agno.models.google import Gemini
from agno.db.in_memory import InMemoryDb

from tools.account_tools import lookup_account
from tools.verification_tools import verify_user
from tools.payment_tools import process_payment
from prompts import SYSTEM_PROMPT
from config import GEMINI_MODEL_ID, GOOGLE_API_KEY, MAX_TOKENS, NUM_HISTORY_RUNS


# ── Default (empty) session state ─────────────────────────────────────────────
_INITIAL_STATE: dict = {
    "stage": "greeting",
    # Account
    "account_id": None,
    "account_found": False,
    "account_data": None,   # Full API response — never sent back to LLM in prompt
    "balance": None,
    # Verification
    "verified": False,
    "verification_attempts": 0,
    # Payment
    "payment_attempts": 0,
    "payment_done": False,
    "transaction_id": None,
}


class Agent:
    """
    Conversational payment collection agent.

    Each instance represents one independent conversation session.
    All state is persisted internally via Agno's InMemoryDb.
    """

    def __init__(self) -> None:
        # Unique session per Agent instance — isolates concurrent conversations
        self._session_id = str(uuid.uuid4())

        if not GOOGLE_API_KEY:
            raise EnvironmentError(
                "GOOGLE_API_KEY is not set. "
                "Add it to your .env file or environment variables."
            )

        self._agno = AgnoAgent(
            model=Gemini(id=GEMINI_MODEL_ID),
            session_state=dict(_INITIAL_STATE), # fresh copy per instance
            db=InMemoryDb(),     
            add_history_to_context=True,
            num_history_runs=NUM_HISTORY_RUNS,
            tools=[lookup_account, verify_user, process_payment],
            instructions=SYSTEM_PROMPT,
            markdown=False,
        )

    # ── Public interface ───────────────────────────────────────────────────────

    def next(self, user_input: str) -> dict:
        """
        Process one turn of the conversation.

        Args:
            user_input: The user's message as a plain string.

        Returns:
            {"message": str}  — the agent's response to display to the user.
        """
        # Guard: if session was terminated by a prior turn, short-circuit
        stage = (self._agno.session_state or {}).get("stage")
        if stage == "terminated":
            return {
                "message": (
                    "This session has been closed for security reasons. "
                    "Please contact our support team for assistance."
                )
            }

        try:
            response = self._agno.run(
                user_input,
                session_id=self._session_id,
            )
            # Agno returns a RunResponse; .content is the agent's text reply
            message = response.content if response and response.content else (
                "I'm sorry, I couldn't generate a response. Please try again."
            )
            return {"message": str(message)}

        except Exception as e:
            # Surface unexpected errors without crashing the evaluation loop
            return {
                "message": (
                    "I encountered an unexpected error. "
                    f"Please try again. (Detail: {e})"
                )
            }
