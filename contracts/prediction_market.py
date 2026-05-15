# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json

MIN_BET           = 0
PROTOCOL_FEE_BPS  = 200      # 2%
CONFIDENCE_BONUS  = "0.10"   # stored as str — no floats at module level
HIGH_CONF         = "0.85"   # stored as str

ALLOWED_CATEGORIES = [
    "economics", "technology", "science", "politics",
    "sports", "climate", "health", "history",
]


# ── JSON helpers ───────────────────────────────────────────────────────────────

def _market_to_json(m: dict) -> str:
    return json.dumps(m, sort_keys=True)

def _json_to_market(s: str) -> dict:
    return json.loads(s)

def _new_market(mid, creator, question, description, hint, category):
    return {
        "id":               mid,
        "creator":          creator,
        "question":         question,
        "description":      description,
        "resolution_hint":  hint,
        "category":         category,
        "status":           "OPEN",
        "outcome":          None,
        "confidence":       None,
        "reasoning":        None,
        "yes_pool":         0,
        "no_pool":          0,
        "yes_bettors":      {},
        "no_bettors":       {},
    }


# ── Contract ───────────────────────────────────────────────────────────────────

class PredictionMarket(gl.Contract):
    markets:      TreeMap[str, str]
    next_id:      u64
    owner:        str
    protocol_fee: u256
    paused:       bool

    def __init__(self) -> None:
        self.next_id      = u64(0)
        self.owner        = str(gl.message.sender_address)
        self.protocol_fee = u256(0)
        self.paused       = False


    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_market(self, market_id: int) -> dict:
        key = str(market_id)
        assert key in self.markets, "Market not found"
        return _json_to_market(self.markets[key])

    def _save_market(self, market_id: int, market: dict) -> None:
        self.markets[str(market_id)] = _market_to_json(market)

    def _sanitize(self, text: str, max_len: int = 400) -> str:
        bad = ["ignore previous", "disregard your", "you are now", "act as if", "system:"]
        lower = text.lower()
        for b in bad:
            assert b not in lower, "Input rejected: disallowed content"
        text = " ".join(text.split())
        assert 10 <= len(text) <= max_len, f"Text must be 10-{max_len} chars"
        return text


    # ── AI Resolution ──────────────────────────────────────────────────────────

    def _resolve_with_ai(self, question: str, description: str,
                         hint: str, category: str) -> dict:

        # Try multiple search angles for better fetch success
        keywords   = " ".join(question.split()[:8])
        search_url = "https://duckduckgo.com/html/?q=" + keywords.replace(" ", "+")
        _url = search_url
        _question = question

        def fetch_evidence():
            try:
                content = gl.nondet.web.render(_url, mode="text")
                return content[:800]
            except Exception:
                return "[fetch failed]"

        def validate_fetch(leader_result) -> bool:
            return isinstance(leader_result, gl.vm.Return)

        evidence = gl.vm.run_nondet(fetch_evidence, validate_fetch)

        # Step 2: reason about outcome
        verdict_prompt = (
            "You are resolving a prediction market question.\n\n"
            f"QUESTION: {question}\n"
            f"DESCRIPTION: {description}\n"
            f"RESOLUTION GUIDANCE: {hint}\n"
            f"CATEGORY: {category}\n\n"
            f"EVIDENCE FROM THE WEB:\n{evidence}\n\n"
            "If web evidence is unavailable, use your training knowledge to answer.\n"
            "Determine:\n"
            "  YES     - the event clearly happened\n"
            "  NO      - the event clearly did NOT happen\n"
            "  INVALID - genuinely impossible to determine even with training knowledge\n\n"
            "Return ONLY this JSON (no markdown):\n"
            '{"outcome":"<YES|NO|INVALID>","confidence":"<float 0.0-1.0 as string>",'
            '"reasoning":"<1-2 sentences>","caveats":"<nuance>"}'
        )
        _vp = verdict_prompt

        def reason_about_outcome():
            raw = gl.nondet.exec_prompt(_vp)
            clean = raw.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.strip()
            try:
                p       = json.loads(clean)
                outcome = str(p.get("outcome", "INVALID")).upper()
                if outcome not in ("YES", "NO", "INVALID"):
                    outcome = "INVALID"
                # confidence stored as string throughout
                raw_conf = p.get("confidence", "0.5")
                conf = float(str(raw_conf))
                conf = max(0.0, min(1.0, conf))
                if conf < 0.55 and outcome != "INVALID":
                    outcome = "INVALID"
                    conf    = 0.5
                return json.dumps({
                    "outcome":   outcome,
                    "confidence": str(round(conf, 2)),
                    "reasoning": str(p.get("reasoning", ""))[:300],
                    "caveats":   str(p.get("caveats", ""))[:150],
                }, sort_keys=True)
            except Exception:
                return json.dumps({
                    "outcome": "INVALID", "confidence": "0.5",
                    "reasoning": "Parse error", "caveats": "",
                }, sort_keys=True)

        def validate_outcome(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            my = reason_about_outcome()
            try:
                l = json.loads(leader_result.calldata)
                m = json.loads(my)
                # Verdict-only comparison — confidence varies across AI models
                return l.get("outcome") == m.get("outcome")
            except Exception:
                return False

        verdict_json = gl.vm.run_nondet(reason_about_outcome, validate_outcome)
        result       = json.loads(verdict_json)
        return {
            "outcome":    result.get("outcome",    "INVALID"),
            "confidence": str(result.get("confidence", "0.5")),
            "reasoning":  result.get("reasoning", ""),
            "caveats":    result.get("caveats",   ""),
        }


    # ── Public Write ───────────────────────────────────────────────────────────

    @gl.public.write
    def create_market(self, question: str, description: str,
                      resolution_hint: str, category: str,
                      duration_blocks: int = 100) -> int:
        assert not self.paused,                 "Contract paused"
        assert category in ALLOWED_CATEGORIES,  f"Invalid category: {category}"

        mid     = int(self.next_id)
        self.next_id = u64(mid + 1)
        creator = str(gl.message.sender_address)

        market = _new_market(
            mid, creator,
            self._sanitize(question, 300),
            self._sanitize(description, 500),
            self._sanitize(resolution_hint, 200),
            category,
        )
        self._save_market(mid, market)
        return mid

    @gl.public.write
    def place_bet(self, market_id: int, position: str) -> None:
        assert not self.paused,            "Contract paused"
        market = self._get_market(market_id)
        assert market["status"] == "OPEN", "Market not open"

        position = position.upper()
        assert position in ("YES", "NO"),  "Position must be YES or NO"

        bet    = gl.message.value
        caller = str(gl.message.sender_address)
        assert bet >= MIN_BET, f"Minimum bet: {MIN_BET}"

        if position == "YES":
            market["yes_pool"] += bet
            prev = market["yes_bettors"].get(caller, 0)
            market["yes_bettors"][caller] = prev + bet
        else:
            market["no_pool"] += bet
            prev = market["no_bettors"].get(caller, 0)
            market["no_bettors"][caller] = prev + bet

        self._save_market(market_id, market)

    @gl.public.write
    def resolve_market(self, market_id: int) -> dict:
        assert not self.paused,            "Contract paused"
        market = self._get_market(market_id)
        assert market["status"] == "OPEN", "Market not in OPEN state"

        result = self._resolve_with_ai(
            market["question"],
            market["description"],
            market["resolution_hint"],
            market["category"],
        )

        market["outcome"]    = result["outcome"]
        market["confidence"] = result["confidence"]
        market["reasoning"]  = {
            "text":    result["reasoning"],
            "caveats": result["caveats"],
        }
        market["status"] = "RESOLVED"
        self._save_market(market_id, market)

        return {
            "market_id":  market_id,
            "outcome":    result["outcome"],
            "confidence": result["confidence"],
        }

    @gl.public.write
    def claim_winnings(self, market_id: int) -> int:
        market = self._get_market(market_id)
        assert market["status"] == "RESOLVED", "Market not resolved"

        caller  = str(gl.message.sender_address)
        outcome = market["outcome"]

        total_pool = market["yes_pool"] + market["no_pool"]
        fee        = int(total_pool * PROTOCOL_FEE_BPS // 10_000)
        dist       = total_pool - fee

        if outcome == "INVALID":
            yes_bet   = market["yes_bettors"].get(caller, 0)
            no_bet    = market["no_bettors"].get(caller, 0)
            total_bet = yes_bet + no_bet
            assert total_bet > 0, "No bet to refund"
            rfee   = int(total_bet * PROTOCOL_FEE_BPS // 10_000)
            payout = total_bet - rfee
            self.protocol_fee = u256(int(self.protocol_fee) + rfee)
            market["yes_bettors"].pop(caller, None)
            market["no_bettors"].pop(caller, None)
            self._save_market(market_id, market)
            gl.message.transfer(Address(caller), payout)
            return payout

        if outcome == "YES":
            bettor_pool  = market["yes_bettors"]
            winning_pool = market["yes_pool"]
        else:
            bettor_pool  = market["no_bettors"]
            winning_pool = market["no_pool"]

        caller_bet = bettor_pool.get(caller, 0)
        assert caller_bet > 0, "No winning bet found"

        # Integer arithmetic only — no floats
        share       = caller_bet * 10_000 // max(winning_pool, 1)
        base_payout = dist * share // 10_000

        # Confidence bonus: +10% if conf >= 0.85
        conf_str = str(market.get("confidence") or "0.0")
        try:
            conf_val = float(conf_str)
        except Exception:
            conf_val = 0.0
        payout = int(base_payout * 110 // 100) if conf_val >= 0.85 else base_payout

        self.protocol_fee = u256(int(self.protocol_fee) + fee)
        bettor_pool.pop(caller)
        self._save_market(market_id, market)
        gl.message.transfer(Address(caller), payout)
        return payout


    # ── Public View ────────────────────────────────────────────────────────────

    @gl.public.view
    def get_market(self, market_id: int) -> dict:
        return self._get_market(market_id)

    @gl.public.view
    def get_all_markets(self) -> list:
        return [_json_to_market(v) for v in self.markets.values()]

    @gl.public.view
    def get_open_markets(self) -> list:
        result = []
        for v in self.markets.values():
            m = _json_to_market(v)
            if m.get("status") == "OPEN":
                result.append(m)
        return result

    @gl.public.view
    def get_market_odds(self, market_id: int) -> dict:
        m     = self._get_market(market_id)
        total = m["yes_pool"] + m["no_pool"]
        if total == 0:
            # Return as strings — no floats in return values
            return {"yes_prob": "0.5", "no_prob": "0.5", "total_pool": 0}
        yes_prob = str(round(m["yes_pool"] / total, 4))
        no_prob  = str(round(m["no_pool"]  / total, 4))
        return {
            "yes_prob":   yes_prob,
            "no_prob":    no_prob,
            "total_pool": total,
        }

    @gl.public.view
    def get_owner(self) -> str:
        return self.owner

    @gl.public.view
    def get_protocol_fees(self) -> int:
        return int(self.protocol_fee)