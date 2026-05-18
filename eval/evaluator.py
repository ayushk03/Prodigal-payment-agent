"""
Automated evaluator for the Payment Collection Agent.

Runs every test case from eval/test_cases.py, checks assertions per turn,
and prints a metrics summary at the end.

Usage:
    python -m eval.evaluator
    # or
    python eval/evaluator.py
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent import Agent
from eval.test_cases import TEST_CASES


# ── Colour helpers ────────────────────────────────────────────────────────────
def green(s):  return f"\033[92m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"


# ── Security check: sensitive fields must never appear in agent messages ──────
SENSITIVE_FIELDS = ["1990-05-14", "1985-11-23", "1992-08-10", "1988-02-29",
                    "4321", "9876", "2468", "1357",
                    "400001", "400002", "400003", "400004"]


def check_no_data_leakage(message: str) -> bool:
    """Returns True if no sensitive data was leaked."""
    return not any(field in message for field in SENSITIVE_FIELDS)


# ── Per-turn evaluation ───────────────────────────────────────────────────────

def run_test_case(tc: dict) -> dict:
    """
    Run a single test case. Returns a result dict with:
      - passed       : bool (all turn assertions + final stage + no leakage)
      - turns_passed : int
      - turns_total  : int
      - leakage      : bool (True = sensitive data found in any message)
      - details      : list of per-turn detail strings
    """
    agent = Agent()
    results = {
        "name": tc["name"],
        "passed": True,
        "turns_passed": 0,
        "turns_total": len(tc["turns"]),
        "leakage": False,
        "details": [],
    }

    for i, (user_input, assertions) in enumerate(tc["turns"]):
        response = agent.next(user_input)
        message = response.get("message", "")

        # Leakage check
        if not check_no_data_leakage(message):
            results["leakage"] = True
            results["passed"] = False
            results["details"].append(
                f"  Turn {i+1} ❌ LEAKAGE detected in: '{message[:120]}'"
            )

        # Assertion checks
        turn_ok = all(fn(message) for fn in assertions)
        if turn_ok:
            results["turns_passed"] += 1
            results["details"].append(
                f"  Turn {i+1} ✓  You: '{user_input[:50]}' → Agent: '{message[:80]}...'"
            )
        else:
            results["passed"] = False
            failed = [fn for fn in assertions if not fn(message)]
            results["details"].append(
                f"  Turn {i+1} ✗  You: '{user_input[:50]}' → Agent: '{message[:80]}...' "
                f"[{len(failed)} assertion(s) failed]"
            )

        # Wait 4.1 seconds to avoid Gemini free-tier rate limits (15 RPM)
        time.sleep(5)

    # Final stage check
    actual_stage = (agent._agno.session_state or {}).get("stage", "unknown")
    expected_stage = tc.get("expect_stage")
    if expected_stage and actual_stage != expected_stage:
        results["passed"] = False
        results["details"].append(
            f"  Stage check ✗  expected='{expected_stage}' actual='{actual_stage}'"
        )
    else:
        results["details"].append(
            f"  Stage check ✓  stage='{actual_stage}'"
        )

    # Transaction ID check
    if tc.get("expect_transaction_id"):
        txn_id = (agent._agno.session_state or {}).get("transaction_id")
        if txn_id:
            results["details"].append(f"  Transaction ID ✓  {txn_id}")
        else:
            results["passed"] = False
            results["details"].append("  Transaction ID ✗  expected but not found")

    return results


# ── Main runner ───────────────────────────────────────────────────────────────

def main():
    print(bold("\n" + "=" * 70))
    print(bold("  Payment Agent — Automated Evaluation"))
    print(bold("=" * 70 + "\n"))

    all_results = []
    for tc in TEST_CASES:
        print(f"Running: {tc['name']} — {tc['description']}")
        result = run_test_case(tc)
        all_results.append(result)
        status = green("PASS") if result["passed"] else red("FAIL")
        print(f"  [{status}] Turns: {result['turns_passed']}/{result['turns_total']}"
              + (f"  {red('⚠ LEAKAGE')}" if result["leakage"] else ""))
        if not result["passed"] or result["leakage"]:
            for line in result["details"]:
                print(line)
        print()

    # ── Metrics summary ────────────────────────────────────────────────────
    total = len(all_results)
    passed = sum(1 for r in all_results if r["passed"])
    leakage_count = sum(1 for r in all_results if r["leakage"])
    turn_pass_rate = (
        sum(r["turns_passed"] for r in all_results)
        / sum(r["turns_total"] for r in all_results)
        * 100
    )

    print(bold("=" * 70))
    print(bold("  Metrics Summary"))
    print(bold("=" * 70))
    print(f"  Test cases passed   : {passed}/{total} ({passed/total*100:.0f}%)")
    print(f"  Turn-level pass rate: {turn_pass_rate:.1f}%")
    print(f"  Sensitive leakage   : {leakage_count} case(s)")
    print()

    # Categorised breakdown
    categories = {
        "Happy Path":              [r for r in all_results if "happy_path" in r["name"]],
        "Verification Failures":   [r for r in all_results if "verification" in r["name"]],
        "Payment Failures":        [r for r in all_results if "payment_" in r["name"]],
        "Messy NL / Edge Cases":   [r for r in all_results if any(
            k in r["name"] for k in ["messy", "out_of_order", "leap", "zero", "long", "account_not"]
        )],
    }
    for cat, results in categories.items():
        if results:
            cat_pass = sum(1 for r in results if r["passed"])
            print(f"  {cat:<28}: {cat_pass}/{len(results)}")

    print(bold("=" * 70 + "\n"))
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
