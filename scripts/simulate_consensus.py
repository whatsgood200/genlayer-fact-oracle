#!/usr/bin/env python3
"""
scripts/simulate_consensus.py
==============================
Local simulation of GenLayer's Optimistic Democracy consensus mechanism.

This script simulates how multiple AI validators (each with different models
and biases) vote on claim verdicts, and how the protocol reaches consensus.

Demonstrates:
  • Multi-validator verdict distribution
  • Confidence-weighted aggregation
  • Conflict resolution
  • Byzantine fault tolerance (up to (n-1)/3 dishonest validators)
  • Effect of validator diversity on accuracy

Run: python scripts/simulate_consensus.py
"""

import json
import random
import statistics
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from collections import Counter


# ── Verdict Types ──────────────────────────────────────────────────────────────

class Verdict(str, Enum):
    TRUE      = "TRUE"
    FALSE     = "FALSE"
    UNCERTAIN = "UNCERTAIN"
    INVALID   = "INVALID"


# ── Validator Models ───────────────────────────────────────────────────────────

@dataclass
class ValidatorProfile:
    """Simulates a GenLayer validator with a specific AI model and bias."""
    name:               str
    model:              str
    accuracy_rate:      float   # probability of correct verdict (0.0–1.0)
    confidence_bias:    float   # how much to inflate confidence (+/-0.1)
    conservative:       bool    # if True, prefers UNCERTAIN over wrong verdict
    response_time_ms:   int     # simulated latency


VALIDATORS = [
    ValidatorProfile("Claude-3.7",   "claude-3-7-sonnet",  0.94, +0.02, True,  120),
    ValidatorProfile("GPT-4o",       "gpt-4o",             0.91, +0.05, False, 150),
    ValidatorProfile("Gemini-1.5",   "gemini-1.5-pro",     0.89, -0.03, True,  200),
    ValidatorProfile("Llama-3.1-70B","llama-3.1-70b",      0.85,  0.00, False,  80),
    ValidatorProfile("Mistral-Large","mistral-large",       0.83, -0.05, True,  100),
]


# ── Claim Scenarios ────────────────────────────────────────────────────────────

@dataclass
class ClaimScenario:
    """A test scenario for the consensus simulation."""
    name:             str
    claim:            str
    category:         str
    ground_truth:     Verdict
    evidence_quality: str       # "HIGH" | "MEDIUM" | "LOW" | "CONFLICTING"
    is_contested:     bool


SCENARIOS = [
    ClaimScenario(
        name             = "Clear Science Fact",
        claim            = "The speed of light in a vacuum is approximately 299,792 km/s.",
        category         = "science",
        ground_truth     = Verdict.TRUE,
        evidence_quality = "HIGH",
        is_contested     = False,
    ),
    ClaimScenario(
        name             = "Economic Prediction",
        claim            = "The US Federal Reserve raised interest rates by 0.25% in March 2024.",
        category         = "economics",
        ground_truth     = Verdict.TRUE,
        evidence_quality = "HIGH",
        is_contested     = False,
    ),
    ClaimScenario(
        name             = "Ambiguous Political Claim",
        claim            = "Country X's economy improved significantly under the current government.",
        category         = "politics",
        ground_truth     = Verdict.UNCERTAIN,
        evidence_quality = "CONFLICTING",
        is_contested     = True,
    ),
    ClaimScenario(
        name             = "Clear False Statement",
        claim            = "The Great Wall of China is visible from the moon with the naked eye.",
        category         = "history",
        ground_truth     = Verdict.FALSE,
        evidence_quality = "HIGH",
        is_contested     = False,
    ),
    ClaimScenario(
        name             = "Opinion Disguised as Fact",
        claim            = "Movie X is objectively the best film ever made.",
        category         = "technology",
        ground_truth     = Verdict.INVALID,
        evidence_quality = "LOW",
        is_contested     = True,
    ),
    ClaimScenario(
        name             = "Low Evidence Claim",
        claim            = "A specific company's internal meeting happened on a precise date.",
        category         = "economics",
        ground_truth     = Verdict.UNCERTAIN,
        evidence_quality = "LOW",
        is_contested     = False,
    ),
]


# ── Validator Simulation ───────────────────────────────────────────────────────

def simulate_validator_vote(
    validator: ValidatorProfile,
    scenario:  ClaimScenario,
    seed:      int,
) -> dict:
    """
    Simulate a single validator's verdict for a claim.

    In production, each GenLayer validator independently runs the contract's
    exec_prompt() call with their specific AI model. Here we simulate the
    statistical distribution of outcomes.
    """
    rng = random.Random(seed + hash(validator.name))

    # Evidence quality affects accuracy
    evidence_modifier = {
        "HIGH":       +0.05,
        "MEDIUM":      0.00,
        "LOW":        -0.15,
        "CONFLICTING": -0.10,
    }.get(scenario.evidence_quality, 0.0)

    effective_accuracy = min(0.99, max(0.5,
        validator.accuracy_rate + evidence_modifier
    ))

    # Determine if this validator gets the right answer
    is_correct = rng.random() < effective_accuracy

    if is_correct:
        verdict = scenario.ground_truth
        base_confidence = rng.uniform(0.75, 0.98)
    else:
        # Wrong answers are typically UNCERTAIN (conservative validators)
        # or a wrong definitive answer (aggressive validators)
        if validator.conservative or scenario.evidence_quality in ("LOW", "CONFLICTING"):
            verdict = Verdict.UNCERTAIN
            base_confidence = rng.uniform(0.50, 0.65)
        else:
            # Pick a random wrong verdict
            wrong_verdicts = [v for v in Verdict if v != scenario.ground_truth]
            verdict = rng.choice(wrong_verdicts)
            base_confidence = rng.uniform(0.55, 0.75)

    # Apply confidence bias
    confidence = min(1.0, max(0.0, base_confidence + validator.confidence_bias))

    return {
        "validator":       validator.name,
        "model":           validator.model,
        "verdict":         verdict.value,
        "confidence":      round(confidence, 3),
        "response_time_ms": validator.response_time_ms + rng.randint(-20, 50),
        "correct":         is_correct,
    }


# ── Consensus Algorithm ────────────────────────────────────────────────────────

def aggregate_consensus(votes: list[dict]) -> dict:
    """
    Simulate GenLayer's Optimistic Democracy consensus algorithm.

    Approach:
      1. Collect all verdicts with confidence weights
      2. Compute weighted vote shares
      3. If highest share > 50%: that verdict wins
      4. If no majority: fall back to UNCERTAIN
      5. Final confidence = weighted avg of agreeing validators

    This mirrors how the EQ principle works: validators compare outputs
    using a semantic equivalence function, not exact string matching.
    """
    if not votes:
        return {"verdict": Verdict.UNCERTAIN.value, "confidence": 0.5, "method": "no_votes"}

    # Weighted tally
    weighted: dict[str, float] = {}
    confidence_sum: dict[str, list[float]] = {}

    for vote in votes:
        v = vote["verdict"]
        w = vote["confidence"]
        weighted[v]         = weighted.get(v, 0.0) + w
        if v not in confidence_sum:
            confidence_sum[v] = []
        confidence_sum[v].append(w)

    total_weight = sum(weighted.values())
    shares       = {v: w / total_weight for v, w in weighted.items()}

    # Find plurality winner
    winner = max(shares, key=shares.get)
    winner_share = shares[winner]

    # Require >50% weighted majority for a definitive verdict
    if winner_share > 0.50:
        avg_conf = statistics.mean(confidence_sum[winner])
        method   = "weighted_majority"
    else:
        # Fallback to UNCERTAIN on split vote
        winner   = Verdict.UNCERTAIN.value
        avg_conf = 0.55
        method   = "fallback_uncertain"

    # Apply uncertainty threshold (mirrors contract logic)
    if avg_conf < 0.55:
        winner   = Verdict.UNCERTAIN.value
        method   = "low_confidence_override"

    return {
        "verdict":     winner,
        "confidence":  round(avg_conf, 3),
        "method":      method,
        "vote_shares": {k: round(v, 3) for k, v in shares.items()},
        "total_votes": len(votes),
    }


# ── Byzantine Fault Simulation ─────────────────────────────────────────────────

def simulate_byzantine_attack(
    validators: list[ValidatorProfile],
    scenario:   ClaimScenario,
    n_byzantine: int,
    seed:       int = 42,
) -> dict:
    """
    Simulate up to n_byzantine malicious validators always voting FALSE
    regardless of evidence. Tests protocol resilience.
    """
    honest_votes = [
        simulate_validator_vote(v, scenario, seed + i)
        for i, v in enumerate(validators[n_byzantine:])
    ]

    byzantine_votes = [
        {
            "validator": f"Byzantine-{i}",
            "model": "adversarial",
            "verdict": "FALSE",   # always attack with FALSE
            "confidence": 0.99,   # high confidence to sway consensus
            "response_time_ms": 50,
            "correct": False,
        }
        for i in range(n_byzantine)
    ]

    all_votes = byzantine_votes + honest_votes
    consensus = aggregate_consensus(all_votes)

    return {
        "scenario":       scenario.name,
        "n_byzantine":    n_byzantine,
        "n_honest":       len(honest_votes),
        "ground_truth":   scenario.ground_truth.value,
        "consensus":      consensus,
        "attack_success": consensus["verdict"] != scenario.ground_truth.value,
    }


# ── Display Helpers ────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"

VERDICT_COLORS = {
    "TRUE":      GREEN,
    "FALSE":     RED,
    "UNCERTAIN": YELLOW,
    "INVALID":   CYAN,
}

def _color_verdict(v: str) -> str:
    return f"{VERDICT_COLORS.get(v, '')}{v}{RESET}"

def _print_separator(char: str = "─", width: int = 70):
    print(f"{DIM}{char * width}{RESET}")

def _print_header(title: str):
    _print_separator("═")
    print(f"{BOLD}  {title}{RESET}")
    _print_separator("═")


# ── Main Simulation ────────────────────────────────────────────────────────────

def run_scenario_simulation(scenario: ClaimScenario, run: int = 0):
    """Run full validator simulation for one scenario."""
    print(f"\n{BOLD}Scenario: {scenario.name}{RESET}")
    print(f"  Claim:            \"{scenario.claim[:70]}{'...' if len(scenario.claim) > 70 else ''}\"")
    print(f"  Ground Truth:     {_color_verdict(scenario.ground_truth.value)}")
    print(f"  Evidence Quality: {scenario.evidence_quality}")
    print(f"  Contested:        {'Yes' if scenario.is_contested else 'No'}")
    _print_separator()

    votes = [
        simulate_validator_vote(v, scenario, seed=run * 100 + i)
        for i, v in enumerate(VALIDATORS)
    ]

    # Print individual votes
    print(f"\n  {'Validator':<20} {'Model':<22} {'Verdict':<12} {'Conf':>6}  {'✓'}")
    print(f"  {'-'*18} {'-'*20} {'-'*10} {'-'*6}  {'-'}")
    for vote in votes:
        check = f"{GREEN}✓{RESET}" if vote["correct"] else f"{RED}✗{RESET}"
        print(f"  {vote['validator']:<20} {vote['model']:<22} "
              f"{_color_verdict(vote['verdict']):<20} {vote['confidence']:>6.3f}  {check}")

    # Consensus
    result = aggregate_consensus(votes)
    print(f"\n  {BOLD}Consensus Result:{RESET}")
    print(f"    Verdict:     {_color_verdict(result['verdict'])}")
    print(f"    Confidence:  {result['confidence']:.3f}")
    print(f"    Method:      {result['method']}")
    print(f"    Vote Shares: {result['vote_shares']}")

    correct = result["verdict"] == scenario.ground_truth.value
    status  = f"{GREEN}CORRECT{RESET}" if correct else f"{RED}WRONG{RESET}"
    print(f"    Accuracy:    {status}")

    return correct, result


def run_byzantine_analysis():
    """Test Byzantine fault tolerance across validator counts."""
    _print_header("BYZANTINE FAULT TOLERANCE ANALYSIS")

    scenario = SCENARIOS[0]  # Clear science fact — easy target for attackers
    print(f"\nAttack Target: \"{scenario.claim[:60]}...\"")
    print(f"Ground Truth: {scenario.ground_truth.value}\n")

    results = []
    for n_byz in range(0, len(VALIDATORS) + 1):
        if n_byz > len(VALIDATORS):
            break
        result = simulate_byzantine_attack(VALIDATORS, scenario, n_byz, seed=42)
        results.append(result)

        status = f"{RED}ATTACK SUCCEEDED{RESET}" if result["attack_success"] else f"{GREEN}Attack Repelled{RESET}"
        print(f"  {n_byz} Byzantine / {result['n_honest']} Honest → "
              f"Consensus: {_color_verdict(result['consensus']['verdict'])} "
              f"({result['consensus']['confidence']:.2f}) → {status}")

    # Summary
    max_tolerated = sum(1 for r in results if not r["attack_success"]) - 1
    print(f"\n  {BOLD}Protocol tolerates up to {max_tolerated} Byzantine validator(s) "
          f"out of {len(VALIDATORS)} total.{RESET}")
    theoretical = (len(VALIDATORS) - 1) // 3
    print(f"  Theoretical BFT limit (⌊(n-1)/3⌋): {theoretical}")


def run_diversity_analysis():
    """Show how validator diversity improves accuracy."""
    _print_header("VALIDATOR DIVERSITY IMPACT")

    scenario = SCENARIOS[2]  # Ambiguous political claim
    print(f"\nScenario: {scenario.name}")
    print(f"Ground Truth: {scenario.ground_truth.value} (ambiguous)\n")

    # Run 10 times and track accuracy
    correct_count = 0
    for i in range(10):
        votes  = [simulate_validator_vote(v, scenario, seed=i*7+j) for j, v in enumerate(VALIDATORS)]
        result = aggregate_consensus(votes)
        if result["verdict"] == scenario.ground_truth.value:
            correct_count += 1

    print(f"  Accuracy over 10 runs: {correct_count}/10 = {correct_count*10}%")
    print(f"  (High UNCERTAIN rate expected for ambiguous claims — this is {GREEN}correct behavior{RESET})")


def run_full_simulation():
    """Run the complete simulation suite."""
    _print_header("GENLAYER FACT ORACLE — CONSENSUS SIMULATION")
    print(f"\n  Validators: {len(VALIDATORS)}")
    print(f"  Scenarios:  {len(SCENARIOS)}")
    print(f"  Models:     {', '.join(v.model for v in VALIDATORS)}\n")

    correct_count = 0
    total         = len(SCENARIOS)

    for i, scenario in enumerate(SCENARIOS):
        correct, _ = run_scenario_simulation(scenario, run=i)
        if correct:
            correct_count += 1

    # Final accuracy report
    _print_separator("═")
    print(f"\n{BOLD}  SIMULATION SUMMARY{RESET}")
    accuracy = correct_count / total * 100
    color    = GREEN if accuracy >= 80 else YELLOW if accuracy >= 60 else RED
    print(f"  Overall Accuracy: {color}{correct_count}/{total} ({accuracy:.0f}%){RESET}")
    print(f"  (Note: UNCERTAIN on ambiguous claims counts as correct)\n")

    # Byzantine analysis
    print()
    run_byzantine_analysis()
    print()

    # Diversity impact
    run_diversity_analysis()

    _print_separator("═")
    print(f"\n{BOLD}  Simulation Complete.{RESET}")
    print(f"  This mirrors GenLayer's Optimistic Democracy: validators run")
    print(f"  independently, and the equivalence principle resolves conflicts.\n")


if __name__ == "__main__":
    run_full_simulation()
