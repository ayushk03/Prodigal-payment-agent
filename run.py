"""
Interactive CLI runner for the Payment Collection Agent.
Usage:
    python run.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add project root to path so `agent` resolves correctly
sys.path.insert(0, os.path.dirname(__file__))

from agent import Agent


def main() -> None:
    print("\n" + "=" * 60)
    print("  Payment Collection Agent  |  type 'quit' to exit")
    print("=" * 60 + "\n")

    agent = Agent()

    # Kick off the conversation with an empty greeting trigger
    opening = agent.next("hello")
    print(f"Agent: {opening['message']}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "bye"}:
            print("Agent: Thank you for using our payment service. Goodbye!")
            break

        response = agent.next(user_input)
        print(f"\nAgent: {response['message']}\n")

        # Auto-exit on session termination or successful completion
        stage = (agent._agno.session_state or {}).get("stage")
        if stage in {"done", "terminated"}:
            break


if __name__ == "__main__":
    main()
