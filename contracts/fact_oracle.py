# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json

MIN_STAKE             = 1_000_000
MAX_CLAIM_LENGTH      = 512
UNCERTAINTY_THRESHOLD = 0.55
WINNER_SHARE          = 0.80
POOL_SHARE            = 0.15
PROTOCOL_FEE          = 0.05

VERDICT_TRUE      = "TRUE"
VERDICT_FALSE     = "FALSE"
VERDICT_UNCERTAIN = "UNCERTAIN"
VERDICT_INVALID   = "INVALID"

ALLOWED_CATEGORIES = [
    "science", "politics", "economics", "sports",
    "technology", "climate", "health", "history",
]

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "disregard your",
    "you are now",
    "pretend you are",
    "act as if",
    "system:",
    "[inst]",
]


def _sanitize(text: str) -> str:
    lower = text.lower()
    for pat in INJECTION_PATTERNS:
        assert pat not in lower, "Claim rejected: disallowed content"
    while "<" in text and ">" in text:
        start = text.find("<")
        end = text.find(">", start)
        if end == -1:
            break
        text = text[:start] + text[end + 1:]
    text = " ".join(text.split())
    assert 10 <= len(text) <= MAX_CLAIM_LENGTH, \
        f"Claim must be 10-{MAX_CLAIM_LENGTH} chars"
    return text


def _claim_to_json(claim: dict) -> str:
    return json.dumps(claim, sort_keys=True)


def _json_to_claim(s: str) -> dict:
    return json.loads(s)


def _lb_to_json(lb: dict) -> str:
    return json.dumps(lb, sort_keys=True)


def _json_to_lb(s: str) -> dict:
    return json.loads(s)


def _new_claim(claim_id, submitter, text, stake, category, deadline_block):
    return {
        "id":              claim_id,
        "submitter":       submitter,
        "text":            text,
        "stake":           stake,
        "challenge_stake": 0,
        "category":        category,
        "deadline_block":  deadline_block,
        "status":          "PENDING",
        "verdict":         None,
        "confidence":      None,
        "evidence":        [],
        "reasoning":       None,
        "challenger":      None,
        "resolved_at":     None,
        "payout_claimed":  False,
    }


class FactOracle(gl.Contract):
    claims:       TreeMap[str, str]
    next_id:      u64
    owner:        str
    paused:       bool
    ins_pool:     u256
    protocol_fee: u256
    leaderboard:  TreeMap[str, str]

    def __init__(self) -> None:
        self.next_id      = u64(0)
        self.owner        = str(gl.message.sender_address)
        self.paused       = False
        self.ins_pool     = u256(0)
        self.protocol_fee = u256(0)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_claim(self, claim_id: int) -> dict:
        key = str(claim_id)
        assert key in self.claims, "Claim not found"
        return _json_to_claim(self.claims[key])

    def _save_claim(self, claim_id: int, claim: dict) -> None:
        self.claims[str(claim_id)] = _claim_to_json(claim)

    def _get_lb(self, addr: str) -> dict:
        if addr in self.leaderboard:
            return _json_to_lb(self.leaderboard[addr])
        return {"correct": 0, "incorrect": 0, "won": 0}

    def _save_lb(self, addr: str, stats: dict) -> None:
        self.leaderboard[addr] = _lb_to_json(stats)

    def _ensure_lb(self, addr: str) -> None:
        if addr not in self.leaderboard:
            self._save_lb(addr, {"correct": 0, "incorrect": 0, "won": 0})

    def _update_leaderboard(self, submitter: str, challenger, verdict: str) -> None:
        self._ensure_lb(submitter)
        if challenger:
            self._ensure_lb(challenger)
        if verdict == VERDICT_TRUE:
            s = self._get_lb(submitter)
            s["correct"] += 1
            self._save_lb(submitter, s)
            if challenger:
                c = self._get_lb(challenger)
                c["incorrect"] += 1
                self._save_lb(challenger, c)
        elif verdict == VERDICT_FALSE:
            s = self._get_lb(submitter)
            s["incorrect"] += 1
            self._save_lb(submitter, s)
            if challenger:
                c = self._get_lb(challenger)
                c["correct"] += 1
                self._save_lb(challenger, c)

    # ── AI resolution core ────────────────────────────────────────────────────

    def _run_ai_resolution(self, claim_text: str, category: str) -> dict:
        # Step 1: generate search queries
        query_prompt = (
            "You are a fact-checking research assistant.\n"
            f'Generate exactly 2 short web search queries to verify: "{claim_text}"\n'
            f"Category: {category}\n\n"
            "Return ONLY a JSON array of exactly 2 strings. No markdown, no explanation.\n"
            'Example: ["query one", "query two"]'
        )
        _qp = query_prompt
        _ct = claim_text

        def generate_queries():
            raw = gl.nondet.exec_prompt(_qp)
            clean = raw.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.strip()
            try:
                queries = json.loads(clean)
                if not isinstance(queries, list) or len(queries) == 0:
                    raise ValueError("not a list")
                queries = [str(q).strip().lower()[:120] for q in queries[:2]]
                if len(queries) == 1:
                    queries = [queries[0], queries[0]]
                return json.dumps(sorted(queries))
            except Exception:
                words = _ct.split()[:6]
                fallback = " ".join(words)
                return json.dumps([fallback, fallback])

        def validate_queries(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            my_result = generate_queries()
            try:
                l = json.loads(leader_result.calldata)
                m = json.loads(my_result)
                return sorted(l) == sorted(m)
            except Exception:
                return False

        queries_json = gl.vm.run_nondet(generate_queries, validate_queries)
        queries = json.loads(queries_json)

        # Step 2: fetch evidence
        evidence_parts = []
        for q in queries[:2]:
            encoded = q.replace(" ", "+")
            search_url = f"https://html.duckduckgo.com/html/?q={encoded}"
            _url = search_url

            def fetch_page():
                try:
                    content = gl.nondet.web.render(_url, mode="text")
                    return content[:800]
                except Exception:
                    return "[fetch failed]"

            def validate_fetch(leader_result) -> bool:
                if not isinstance(leader_result, gl.vm.Return):
                    return False
                my_result = fetch_page()
                # Accept if both fetched something (not both failed)
                return not (my_result == "[fetch failed]" and
                            leader_result.calldata == "[fetch failed]")

            snippet = gl.vm.run_nondet(fetch_page, validate_fetch)
            evidence_parts.append(f"Query: {q}\n{snippet}")

        evidence_block = "\n\n---\n\n".join(evidence_parts) or "No evidence."

        # Step 3: reason and produce verdict
        verdict_prompt = (
            "You are an expert fact-checker.\n\n"
            f'CLAIM: "{claim_text}"\n'
            f"CATEGORY: {category}\n\n"
            f"EVIDENCE:\n{evidence_block}\n\n"
            "Analyze and return ONLY this JSON (no markdown):\n"
            '{"verdict":"<TRUE|FALSE|UNCERTAIN|INVALID>",'
            '"confidence":<float 0.0-1.0>,'
            '"key_evidence":"<one sentence>",'
            '"caveats":"<nuance>"}'
        )
        _vp = verdict_prompt

        def reason_about_claim():
            raw = gl.nondet.exec_prompt(_vp)
            clean = raw.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.strip()
            try:
                parsed = json.loads(clean)
                verdict = str(parsed.get("verdict", VERDICT_UNCERTAIN)).upper()
                if verdict not in (VERDICT_TRUE, VERDICT_FALSE,
                                   VERDICT_UNCERTAIN, VERDICT_INVALID):
                    verdict = VERDICT_UNCERTAIN
                conf = float(parsed.get("confidence", 0.5))
                conf = max(0.0, min(1.0, conf))
                if conf < UNCERTAINTY_THRESHOLD:
                    verdict = VERDICT_UNCERTAIN
                return json.dumps({
                    "verdict":      verdict,
                    "confidence":   str(round(conf, 2)),
                    "key_evidence": str(parsed.get("key_evidence", ""))[:200],
                    "caveats":      str(parsed.get("caveats", ""))[:150],
                }, sort_keys=True)
            except Exception:
                return json.dumps({
                    "verdict":      VERDICT_UNCERTAIN,
                    "confidence":   "0.5",
                    "key_evidence": "Parse error",
                    "caveats":      "AI output could not be parsed",
                }, sort_keys=True)

        def validate_verdict(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            my_result = reason_about_claim()
            try:
                l = json.loads(leader_result.calldata)
                m = json.loads(my_result)
                # Equivalent if same verdict and confidence within 0.2
                return (l.get("verdict") == m.get("verdict") and
                        abs(float(l.get("confidence", 0.5)) -
                            float(m.get("confidence", 0.5))) <= 0.2)
            except Exception:
                return False

        verdict_json = gl.vm.run_nondet(reason_about_claim, validate_verdict)
        result = json.loads(verdict_json)
        return {
            "verdict":       result.get("verdict",      VERDICT_UNCERTAIN),
            "confidence":    str(result.get("confidence", "0.5")),
            "key_evidence":  result.get("key_evidence", ""),
            "caveats":       result.get("caveats",      ""),
            "evidence_urls": [
                "https://html.duckduckgo.com/html/?q=" + q.replace(" ", "+")
                for q in queries
            ],
        }

    # ── Public write methods ──────────────────────────────────────────────────

    @gl.public.write
    def submit_claim(self, text: str, category: str, challenge_blocks: int = 20) -> int:
        assert not self.paused, "Contract paused"
        assert category in ALLOWED_CATEGORIES, f"Invalid category: {category}"
        assert 5 <= challenge_blocks <= 500, "Challenge period: 5-500 blocks"
        sender = str(gl.message.sender_address)
        stake  = gl.message.value
        assert stake >= MIN_STAKE, f"Minimum stake: {MIN_STAKE}"
        clean = _sanitize(text)
        cid = int(self.next_id)
        self.next_id = u64(cid + 1)
        deadline = 0  # block tracking disabled for testing
        claim = _new_claim(cid, sender, clean, stake, category, deadline)
        self._save_claim(cid, claim)
        self._ensure_lb(sender)
        return cid

    @gl.public.write
    def challenge_claim(self, claim_id: int) -> None:
        assert not self.paused, "Contract paused"
        claim = self._get_claim(claim_id)
        assert claim["status"] == "PENDING",  "Claim not pending"
        assert claim["challenger"] is None,   "Already has a challenger"
        # assert gl.message.block_number <= claim["deadline_block"], "Challenge window closed"
        sender = str(gl.message.sender_address)
        stake  = gl.message.value
        assert sender != claim["submitter"],  "Cannot challenge your own claim"
        assert stake >= claim["stake"],       "Match or exceed the claim stake"
        claim["challenger"]      = sender
        claim["challenge_stake"] = stake
        claim["status"]          = "DISPUTED"
        self._save_claim(claim_id, claim)
        self._ensure_lb(sender)

    @gl.public.write
    def resolve_claim(self, claim_id: int) -> dict:
        assert not self.paused, "Contract paused"
        claim = self._get_claim(claim_id)
        assert claim["status"] in ("PENDING", "DISPUTED"), \
            f"Cannot resolve claim in status: {claim['status']}"
        result = self._run_ai_resolution(claim["text"], claim["category"])
        claim["verdict"]     = result["verdict"]
        claim["confidence"]  = result["confidence"]
        claim["evidence"]    = result["evidence_urls"]
        claim["reasoning"]   = {
            "key_evidence": result["key_evidence"],
            "caveats":      result["caveats"],
        }
        claim["status"]      = "RESOLVED"
        claim["resolved_at"] = 0
        self._save_claim(claim_id, claim)
        self._update_leaderboard(
            claim["submitter"],
            claim.get("challenger"),
            result["verdict"],
        )
        return {
            "claim_id":   claim_id,
            "verdict":    result["verdict"],
            "confidence": str(result["confidence"]),
        }

    @gl.public.write
    def claim_payout(self, claim_id: int) -> int:
        claim = self._get_claim(claim_id)
        assert claim["status"] == "RESOLVED", "Not resolved yet"
        assert not claim["payout_claimed"],   "Already claimed"
        sender  = str(gl.message.sender_address)
        verdict = claim["verdict"]
        total   = claim["stake"] + claim["challenge_stake"]
        fee     = int(total * PROTOCOL_FEE)
        pool    = int(total * POOL_SHARE)
        winner  = total - fee - pool
        payout  = 0
        if not claim["challenger"]:
            assert sender == claim["submitter"], "Only submitter can collect"
            payout = claim["stake"] - fee
        elif verdict == VERDICT_TRUE:
            assert sender == claim["submitter"], "Submitter wins on TRUE"
            payout = winner
        elif verdict == VERDICT_FALSE:
            assert sender == claim["challenger"], "Challenger wins on FALSE"
            payout = winner
        else:
            if sender == claim["submitter"]:
                payout = int(claim["stake"] * (1 - PROTOCOL_FEE))
            elif sender == claim["challenger"]:
                payout = int(claim["challenge_stake"] * (1 - PROTOCOL_FEE))
            else:
                assert False, "You are not a party to this claim"
        self.protocol_fee = u256(int(self.protocol_fee) + fee)
        self.ins_pool     = u256(int(self.ins_pool) + pool)
        claim["payout_claimed"] = True
        self._save_claim(claim_id, claim)
        lb = self._get_lb(sender)
        lb["won"] += payout
        self._save_lb(sender, lb)
        gl.message.transfer(Address(sender), payout)
        return payout

    @gl.public.write
    def expire_claim(self, claim_id: int) -> None:
        claim = self._get_claim(claim_id)
        assert claim["status"] == "PENDING", "Only PENDING claims can expire"
        pass  # block check disabled for testing
        fee    = int(claim["stake"] * PROTOCOL_FEE)
        refund = claim["stake"] - fee
        self.protocol_fee = u256(int(self.protocol_fee) + fee)
        claim["status"]      = "EXPIRED"
        claim["resolved_at"] = 0
        self._save_claim(claim_id, claim)
        gl.message.transfer(Address(claim["submitter"]), refund)

    # ── Public view methods ───────────────────────────────────────────────────

    @gl.public.view
    def get_claim(self, claim_id: int) -> dict:
        return self._get_claim(claim_id)

    @gl.public.view
    def get_all_claims(self) -> list:
        result = []
        for v in self.claims.values():
            result.append(_json_to_claim(v))
        return result

    @gl.public.view
    def get_stats(self) -> dict:
        all_claims = self.get_all_claims()
        resolved   = [c for c in all_claims if c["status"] == "RESOLVED"]
        total_conf = sum(float(c["confidence"]) for c in resolved if c["confidence"] is not None)
        avg_conf   = str(round(total_conf / max(len(resolved), 1), 3))
        return {
            "total":          len(all_claims),
            "resolved":       len(resolved),
            "avg_confidence": avg_conf,
            "ins_pool":       int(self.ins_pool),
            "protocol_fee":   int(self.protocol_fee),
            "paused":         self.paused,
        }

    @gl.public.view
    def get_leaderboard(self) -> list:
        entries = []
        for addr, stats_json in self.leaderboard.items():
            stats = _json_to_lb(stats_json)
            entries.append({"address": addr, **stats})
        return sorted(entries, key=lambda x: x["won"], reverse=True)

    @gl.public.view
    def get_owner(self) -> str:
        return self.owner