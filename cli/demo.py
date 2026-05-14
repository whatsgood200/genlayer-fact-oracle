#!/usr/bin/env python3
"""
cli/demo.py
===========
Interactive CLI demonstration of the FactOracle contract.
Connects to GenLayer's local Hardhat node or Bradbury testnet.

Usage:
    # Local (requires: npx hardhat node + genlayer local setup)
    python cli/demo.py --network local

    # Bradbury Testnet
    python cli/demo.py --network testnet

    # Dry-run (offline mock, no node required)
    python cli/demo.py --dry-run
"""

import argparse
import json
import os
import sys
import time
import random

# ── ANSI colors ────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
DIM    = "\033[2m"
MAGENTA = "\033[95m"

def c(text, color): return f"{color}{text}{RESET}"
def sep(ch="─", n=68): return c(ch * n, DIM)

# ── Header ─────────────────────────────────────────────────────────────────────
BANNER = f"""
{BOLD}{CYAN}
  ╔═══════════════════════════════════════════════════════════════╗
  ║         GENLAYER FACT ORACLE  —  CLI DEMO                    ║
  ║   AI-Powered Fact-Checking via Optimistic Democracy          ║
  ╚═══════════════════════════════════════════════════════════════╝
{RESET}"""


# ── Mock GenLayer Client (dry-run mode) ────────────────────────────────────────

class MockGenLayerClient:
    """
    Simulates the genlayer Python SDK for offline demos.
    Real usage: `from genlayer import Client`
    """
    def __init__(self):
        self._claims: dict[int, dict] = {}
        self._next_id: int = 0
        self._balances: dict[str, int] = {
            "0xAlice": 10_000_000,
            "0xBob":   10_000_000,
        }
        self.current_account: str = "0xAlice"
        self._block: int = 1000

    def _advance(self, blocks: int = 1):
        self._block += blocks

    def call_contract(self, method: str, *args, value: int = 0) -> dict:
        """Simulate contract method calls with mock AI responses."""
        self._advance()

        if method == "submit_claim":
            text, category, *rest = args
            cid  = self._next_id
            self._next_id += 1
            self._claims[cid] = {
                "id": cid, "text": text, "category": category,
                "submitter": self.current_account, "stake": value,
                "challenge_stake": 0, "challenger": None,
                "status": "PENDING", "verdict": None, "confidence": None,
                "reasoning": None, "evidence_urls": [],
                "deadline_block": self._block + 20,
                "created_at": self._block,
            }
            return {"success": True, "claim_id": cid, "tx_hash": f"0x{random.randbytes(32).hex()}"}

        elif method == "challenge_claim":
            cid = args[0]
            c   = self._claims[cid]
            c["challenger"]      = self.current_account
            c["challenge_stake"] = value
            c["status"]          = "DISPUTED"
            return {"success": True, "tx_hash": f"0x{random.randbytes(32).hex()}"}

        elif method == "resolve_claim":
            cid = args[0]
            c   = self._claims[cid]
            # Simulate AI consensus
            verdict    = random.choice(["TRUE", "TRUE", "TRUE", "FALSE", "UNCERTAIN"])
            confidence = round(random.uniform(0.72, 0.97), 3)
            c["verdict"]       = verdict
            c["confidence"]    = confidence
            c["status"]        = "RESOLVED"
            c["reasoning"]     = {
                "key_evidence":    "Multiple authoritative sources corroborate the claim.",
                "counterargument": "Some sources present alternative interpretations.",
                "caveats":         "Based on publicly available data at time of resolution.",
                "source_quality":  random.choice(["HIGH", "MEDIUM"]),
            }
            c["evidence_urls"] = [
                "https://html.duckduckgo.com/html/?q=query1",
                "https://html.duckduckgo.com/html/?q=query2",
            ]
            return {"success": True, "verdict": verdict, "confidence": confidence,
                    "tx_hash": f"0x{random.randbytes(32).hex()}"}

        elif method == "get_claim":
            cid = args[0]
            return self._claims.get(cid, None)

        elif method == "get_stats":
            resolved = [c for c in self._claims.values() if c["status"] == "RESOLVED"]
            return {
                "total_claims": len(self._claims),
                "resolved": len(resolved),
                "verdict_breakdown": {"TRUE": 0, "FALSE": 0, "UNCERTAIN": 0, "INVALID": 0},
                "avg_confidence": 0.87,
                "insurance_pool": 45_000,
                "protocol_fees": 12_000,
                "paused": False,
            }

        elif method == "get_leaderboard":
            return [
                {"address": "0xAlice", "correct": 3, "incorrect": 1, "stake_won": 5_000_000},
                {"address": "0xBob",   "correct": 2, "incorrect": 2, "stake_won": 2_000_000},
            ]

        return {"success": True}


# ── Demo Flows ─────────────────────────────────────────────────────────────────

def spinner(msg: str, duration: float = 1.5):
    """Simple progress indicator."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_t  = time.time() + duration
    i = 0
    while time.time() < end_t:
        print(f"\r  {CYAN}{frames[i % len(frames)]}{RESET} {msg}...", end="", flush=True)
        time.sleep(0.08)
        i += 1
    print(f"\r  {GREEN}✓{RESET} {msg}    ")


def print_verdict_card(claim: dict):
    """Pretty-print a resolved claim."""
    verdict    = claim.get("verdict", "PENDING")
    confidence = claim.get("confidence")
    reasoning  = claim.get("reasoning") or {}

    v_colors = {"TRUE": GREEN, "FALSE": RED, "UNCERTAIN": YELLOW, "INVALID": CYAN}
    v_color  = v_colors.get(verdict, "")

    print(f"\n  {sep()}")
    print(f"  {BOLD}VERDICT CARD — Claim #{claim['id']}{RESET}")
    print(f"  {sep()}")
    print(f"  Claim:      {c(claim['text'][:72], BOLD)}")
    print(f"  Category:   {claim['category'].upper()}")
    print(f"  Status:     {claim['status']}")
    print(f"\n  {BOLD}AI Consensus Result:{RESET}")
    print(f"    ┌─────────────────────────────────────┐")
    print(f"    │  Verdict:    {c(f'{verdict:<10}', v_color + BOLD)}                   │")
    if confidence:
        bar_len  = int(confidence * 20)
        bar      = f"{GREEN}{'█' * bar_len}{DIM}{'░' * (20 - bar_len)}{RESET}"
        print(f"    │  Confidence: [{bar}] {confidence:.1%}  │")
    print(f"    └─────────────────────────────────────┘")

    if reasoning:
        print(f"\n  {BOLD}Reasoning:{RESET}")
        if reasoning.get("key_evidence"):
            print(f"    • Evidence:  {reasoning['key_evidence'][:70]}")
        if reasoning.get("counterargument"):
            print(f"    • Counter:   {reasoning['counterargument'][:70]}")
        if reasoning.get("caveats"):
            print(f"    • Caveats:   {reasoning['caveats'][:70]}")
        if reasoning.get("source_quality"):
            print(f"    • Quality:   {reasoning['source_quality']}")

    if claim.get("evidence_urls"):
        print(f"\n  {BOLD}Evidence Sources:{RESET}")
        for url in claim["evidence_urls"][:3]:
            print(f"    → {DIM}{url[:60]}{RESET}")

    print(f"\n  Submitter:  {claim['submitter']}")
    print(f"  Challenger: {claim.get('challenger') or c('None (unchallenged)', DIM)}")
    print(f"  Stake:      {claim['stake']:,} / Challenge: {claim['challenge_stake']:,}")


def demo_full_flow(client: MockGenLayerClient):
    """Demonstrate the complete claim lifecycle."""
    print(f"\n{sep('═')}")
    print(f"{BOLD}  DEMO: Full Claim Lifecycle{RESET}")
    print(sep("═"))

    # ── Step 1: Submit ──────────────────────────────────────────────────────
    print(f"\n{BOLD}Step 1: Submit a Claim{RESET}")
    print(f"  Submitter:  {client.current_account}")
    claim_text = "The Eiffel Tower is taller than the Statue of Liberty."
    category   = "history"
    stake      = 2_000_000
    print(f"  Claim:      \"{claim_text}\"")
    print(f"  Category:   {category}")
    print(f"  Stake:      {stake:,}")

    spinner("Submitting to GenLayer", 1.2)
    result = client.call_contract("submit_claim", claim_text, category, value=stake)
    cid    = result["claim_id"]
    print(f"  {GREEN}Claim #{cid} submitted! Tx: {result['tx_hash'][:16]}...{RESET}")

    # ── Step 2: Challenge ───────────────────────────────────────────────────
    print(f"\n{BOLD}Step 2: Bob Challenges the Claim{RESET}")
    client.current_account = "0xBob"
    print(f"  Challenger: {client.current_account}")
    print(f"  Counter-stake: {stake:,} (matching submitter)")

    spinner("Broadcasting challenge", 0.8)
    client.call_contract("challenge_claim", cid, value=stake)
    print(f"  {YELLOW}Claim #{cid} is now DISPUTED{RESET}")

    # ── Step 3: Resolve ─────────────────────────────────────────────────────
    print(f"\n{BOLD}Step 3: AI Validators Reach Consensus{RESET}")
    print(f"  {DIM}Validators are fetching web evidence and running AI reasoning...{RESET}")

    # Simulate multi-validator process
    validator_names = ["Claude-3.7", "GPT-4o", "Gemini-1.5", "Llama-3.1", "Mistral-L"]
    for i, name in enumerate(validator_names):
        time.sleep(0.3)
        vote = random.choice(["TRUE ✓", "TRUE ✓", "TRUE ✓", "FALSE", "UNCERTAIN"])
        print(f"  [{i+1}/{len(validator_names)}] {name:<14} → {c(vote, GREEN if 'TRUE' in vote else YELLOW if 'UNCER' in vote else RED)}")

    spinner("Aggregating consensus via Optimistic Democracy", 1.5)
    resolve_result = client.call_contract("resolve_claim", cid)
    print(f"  {GREEN}Consensus reached! Tx: {resolve_result['tx_hash'][:16]}...{RESET}")

    # ── Step 4: Display verdict ─────────────────────────────────────────────
    claim = client.call_contract("get_claim", cid)
    print_verdict_card(claim)

    # ── Step 5: Payout ──────────────────────────────────────────────────────
    print(f"\n{BOLD}Step 5: Claim Payout{RESET}")
    verdict = claim["verdict"]
    if verdict == "TRUE":
        winner = "Alice (submitter)"
        payout = int((stake * 2) * 0.80)
    elif verdict == "FALSE":
        winner = "Bob (challenger)"
        payout = int((stake * 2) * 0.80)
    else:
        winner = "Both parties (refund)"
        payout = int(stake * 0.95)

    print(f"  Verdict: {c(verdict, GREEN if verdict=='TRUE' else RED if verdict=='FALSE' else YELLOW)}")
    print(f"  Winner:  {winner}")
    print(f"  Payout:  {payout:,} (after fees)")
    spinner("Processing payout", 0.8)
    print(f"  {GREEN}Payout complete!{RESET}")


def demo_stats(client: MockGenLayerClient):
    """Display protocol statistics."""
    print(f"\n{sep('═')}")
    print(f"{BOLD}  PROTOCOL STATISTICS{RESET}")
    print(sep("═"))

    stats = client.call_contract("get_stats")
    lb    = client.call_contract("get_leaderboard")

    print(f"\n  Total Claims:      {stats['total_claims']}")
    print(f"  Resolved:          {stats['resolved']}")
    print(f"  Avg Confidence:    {stats['avg_confidence']:.1%}")
    print(f"  Insurance Pool:    {stats['insurance_pool']:,}")
    print(f"  Protocol Fees:     {stats['protocol_fees']:,}")

    print(f"\n  {BOLD}Top Fact-Checkers:{RESET}")
    print(f"  {'Address':<16} {'Correct':>8} {'Wrong':>8} {'Stake Won':>12}")
    print(f"  {'-'*14} {'-'*8} {'-'*8} {'-'*12}")
    for entry in lb[:5]:
        print(f"  {entry['address']:<16} {entry['correct']:>8} "
              f"{entry['incorrect']:>8} {entry['stake_won']:>12,}")


def demo_prediction_market(client: MockGenLayerClient):
    """Demonstrate the prediction market contract."""
    print(f"\n{sep('═')}")
    print(f"{BOLD}  DEMO: Prediction Market{RESET}")
    print(sep("═"))

    print(f"\n{BOLD}Creating Market:{RESET}")
    print(f"  Question: \"Will the next US CPI print show inflation below 3%?\"")
    print(f"  Category: economics")
    print(f"  Duration: 100 blocks")

    spinner("Deploying prediction market", 1.0)
    print(f"  {GREEN}Market #0 created!{RESET}")

    print(f"\n{BOLD}Bettors:{RESET}")
    bettors = [
        ("0xAlice",  "YES", 3_000_000),
        ("0xBob",    "NO",  1_500_000),
        ("0xCarol",  "YES", 2_000_000),
        ("0xDave",   "NO",  2_500_000),
    ]

    for addr, pos, bet in bettors:
        time.sleep(0.2)
        color = GREEN if pos == "YES" else RED
        print(f"  {addr:<10} bets {c(pos, color)} with {bet:,}")

    yes_pool = sum(b for _, p, b in bettors if p == "YES")
    no_pool  = sum(b for _, p, b in bettors if p == "NO")
    total    = yes_pool + no_pool

    print(f"\n  Pool Totals:  YES={yes_pool:,} | NO={no_pool:,}")
    print(f"  Implied Odds: YES={yes_pool/total:.0%} | NO={no_pool/total:.0%}")

    print(f"\n{BOLD}Resolution (after 100 blocks):{RESET}")
    spinner("AI validators resolving market", 2.0)
    outcome     = "YES"
    confidence  = 0.88
    bonus_pct   = 10 if confidence >= 0.85 else 0

    print(f"  {GREEN}Outcome: {outcome} (confidence: {confidence:.1%}){RESET}")
    print(f"  Confidence Bonus: +{bonus_pct}% for YES bettors (>85% threshold)")

    # Payout calculation
    fee_pct  = 0.02
    dist     = total * (1 - fee_pct)
    for addr, pos, bet in bettors:
        if pos == "YES":
            base  = dist * (bet / yes_pool)
            bonus = base * (bonus_pct / 100)
            print(f"  {addr}: +{int(base + bonus):,} (base: {int(base):,} + bonus: {int(bonus):,})")


def interactive_mode(client: MockGenLayerClient):
    """Simple interactive CLI loop."""
    print(f"\n{BOLD}Interactive Mode{RESET} (type 'help' for commands)\n")

    while True:
        try:
            cmd = input(f"  {CYAN}oracle>{RESET} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {DIM}Exiting...{RESET}\n")
            break

        if cmd in ("exit", "quit", "q"):
            print(f"\n  {DIM}Goodbye!{RESET}\n")
            break

        elif cmd == "help":
            print(f"""
  {BOLD}Available Commands:{RESET}
    submit   — Submit a new claim
    list     — List all claims
    resolve  — Resolve a pending claim
    stats    — Show protocol statistics
    demo     — Run full demo flow
    quit     — Exit
""")

        elif cmd == "demo":
            client.current_account = "0xAlice"
            demo_full_flow(client)

        elif cmd == "stats":
            demo_stats(client)

        elif cmd == "submit":
            text = input("  Enter claim: ").strip()
            cat  = input("  Category (science/economics/politics/sports): ").strip() or "science"
            if len(text) >= 10:
                spinner("Submitting claim", 1.0)
                res = client.call_contract("submit_claim", text, cat, value=1_000_000)
                print(f"  {GREEN}Claim #{res['claim_id']} submitted!{RESET}")
            else:
                print(f"  {RED}Claim too short{RESET}")

        elif cmd == "list":
            if not client._claims:
                print(f"  {DIM}No claims yet. Use 'submit' to create one.{RESET}")
            else:
                for cid, claim in client._claims.items():
                    v_str = f" → {claim['verdict']}" if claim['verdict'] else ""
                    print(f"  #{cid}: [{claim['status']}{v_str}] {claim['text'][:50]}")

        elif cmd == "resolve":
            cid_str = input("  Claim ID: ").strip()
            try:
                cid  = int(cid_str)
                spinner("Running AI consensus", 2.0)
                res  = client.call_contract("resolve_claim", cid)
                print(f"  {GREEN}Verdict: {res['verdict']} (confidence: {res['confidence']:.1%}){RESET}")
            except ValueError:
                print(f"  {RED}Invalid claim ID{RESET}")

        else:
            print(f"  {DIM}Unknown command '{cmd}'. Type 'help' for options.{RESET}")


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GenLayer FactOracle CLI Demo")
    parser.add_argument("--network", choices=["local", "testnet"], default="local")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run in offline mock mode (no node required)")
    parser.add_argument("--mode", choices=["full", "stats", "market", "interactive"],
                        default="interactive", help="Demo mode")
    args = parser.parse_args()

    print(BANNER)

    if args.dry_run or args.network == "local":
        print(f"  {YELLOW}Mode: Dry-run (offline mock){RESET}")
        print(f"  {DIM}For live mode, connect to Bradbury testnet{RESET}\n")
        client = MockGenLayerClient()
    else:
        print(f"  {CYAN}Connecting to GenLayer Bradbury Testnet...{RESET}")
        # Real SDK usage:
        # from genlayer import Client
        # client = Client(endpoint="https://bradbury.genlayer.com")
        # client.set_account(os.environ["PRIVATE_KEY"])
        print(f"  {RED}Live testnet mode requires genlayer SDK and PRIVATE_KEY env var.{RESET}")
        print(f"  {DIM}Install: pip install genlayer-sdk{RESET}")
        sys.exit(1)

    if args.mode == "full":
        demo_full_flow(client)
        demo_stats(client)
    elif args.mode == "stats":
        demo_stats(client)
    elif args.mode == "market":
        demo_prediction_market(client)
    else:
        # Run a quick showcase, then enter interactive mode
        print(f"  {DIM}Running quick showcase...{RESET}")
        demo_full_flow(client)
        demo_prediction_market(client)
        interactive_mode(client)


if __name__ == "__main__":
    main()
