# GenLayer Intelligent Contract Developer Guide
## Deployment, Debugging & Production Patterns

> Hard-won debugging knowledge from building FactOracle and PredictionMarket on Bradbury Testnet.
> This comes from real errors and fixes.

---

## The Correct Magic Comment

```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

`py-genlayer:test` does **not** resolve correctly on current Studio or Bradbury. Use the hash above.

---

## Confirmed Working API (Bradbury Testnet)

```python
# Sender address — returns Address object, MUST wrap in str()
owner = str(gl.message.sender_address)

# Transaction value
stake = gl.message.value

# LLM call
result = gl.nondet.exec_prompt(prompt)

# Web fetch
content = gl.nondet.web.render(url, mode="text")

# Consensus
result = gl.vm.run_nondet(leader_fn, validator_fn)

# Transfer
gl.message.transfer(Address(sender_str), amount)
```

## API Calls That Do NOT Exist (will crash your contract)

```python
# These do not exist — do not use them
gl.block.number
gl.message.block_number
gl.message.sender_account
gl.message.sender_account.as_hex
gl.eq_principle.strict_eq()
gl.eq_principle.prompt_comparative()
gl.nondet.web.render()           # wrong namespace
gl.nondet.exec_prompt()          # wrong namespace
```

---

## Storage Type Rules

GenVM enforces strict type annotations on all contract state variables.

### ✅ Allowed storage types
```python
class MyContract(gl.Contract):
    name:         str
    count:        u64
    balance:      u256
    active:       bool
    data:         TreeMap[str, str]    # fully specified generics only
    ids:          DynArray[str]
```

###  Forbidden storage types
```python
class MyContract(gl.Contract):
    count:    int          # use u64 or u256
    items:    list         # use DynArray[str]
    record:   dict         # not a valid persistent type
    pool:     bigint       # causes schema load failure
    data:     TreeMap      # bare generic — must specify types
```

### Storing complex data (dicts, lists)
Serialize to JSON string and store in `TreeMap[str, str]`:

```python
import json

claims: TreeMap[str, str]

def _save(self, id: int, record: dict) -> None:
    self.claims[str(id)] = json.dumps(record, sort_keys=True)

def _load(self, id: int) -> dict:
    assert str(id) in self.claims, "Not found"
    return json.loads(self.claims[str(id)])
```

---

## Float Rules

**No Python floats anywhere in contract code.** This includes:
- Storage annotations
- Return values from public methods
- Module-level constants used in storage

```python
#  Will crash with "not calldata encodable 1.0: float"
confidence: float = 0.95
return {"confidence": 0.95}

# ✅ Store and return as strings
confidence: str = "0.95"
return {"confidence": "0.95"}

# ✅ Module-level constants used in runtime math are fine
PROTOCOL_FEE = 0.05   # only used in calculations, not stored/returned directly
```

---

## Consensus Pattern

All non-deterministic calls (LLM, web) must be inside inner functions passed to `gl.vm.run_nondet`.

```python
def _run_ai_check(self, claim: str) -> str:
    _prompt = f"Is this true? {claim}. Reply YES or NO."

    def leader_fn():
        raw = gl.nondet.exec_prompt(_prompt)
        return raw.strip().upper()[:3]  # "YES" or "NO"

    def validator_fn(leader_result) -> bool:
        if not isinstance(leader_result, gl.vm.Return):
            return False
        my_result = leader_fn()
        # Compare only the verdict — not confidence or phrasing
        return leader_result.calldata == my_result

    return gl.vm.run_nondet(leader_fn, validator_fn)
```

### Critical rules for inner functions:
1. **Never access `self` inside inner functions** — capture needed values in local variables before defining the function
2. **Use closure variables** for any data the inner function needs
3. **`validator_fn` must return `bool`**
4. **`leader_result.calldata`** contains the leader's return value as a string

---

## Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `AttributeError: 'Address' object has no attribute 'encode'` | Storing `gl.message.sender_address` directly in `str` field | `str(gl.message.sender_address)` |
| `TypeError: not calldata encodable 1.0: float` | Returning Python float in public method | Convert all floats to strings before returning |
| `AttributeError: module 'genlayer.gl' has no attribute 'block'` | `gl.block.number` doesn't exist | Block tracking not available yet — store 0 |
| `AttributeError: 'MessageType' object has no attribute 'sender_account'` | Wrong attribute name | Use `gl.message.sender_address` |
| `Could not load contract schema` | Invalid storage type annotation | Check all class-level type annotations |
| `FINISHED_WITH_ERROR` + `ACCEPTED` + `AGREE` | `__init__` crashed at runtime | Check API calls and storage types |
| `ValueError: called non-payable method with non-zero value` | Sending ETH value to non-payable method | Set transaction value to 0 |
| `Contract IdlenessPhase not found` | Studio backend cold-start | Hard refresh browser, wait 30 seconds |
| `AssertionError: Challenge period: 5-500 blocks` | Frontend sending 0 for block param | Remove the assertion or set default |

---

## Deployment Checklist

```
[ ] Magic comment uses long hash (not py-genlayer:test)
[ ] No float values in storage type annotations
[ ] No float values in public method return values
[ ] All sender_address calls wrapped in str()
[ ] All TreeMap types fully specified: TreeMap[str, str]
[ ] No bare int in storage — use u64 or u256
[ ] No dict or list in storage — use TreeMap[str, str] + JSON
[ ] All non-det calls inside inner functions
[ ] No self access inside inner functions
[ ] validate_fn returns bool
[ ] Tested in Studio Leader Only mode first
[ ] Tested in Studio Full Consensus mode
[ ] Deployed to Bradbury
[ ] Frontend transaction value set to BigInt(0)
```

---

## Frontend Integration (genlayer-js)

```javascript
import { createClient } from "genlayer-js";
import { testnetBradbury } from "genlayer-js/chains";
import { TransactionStatus } from "genlayer-js/types";

// Connect MetaMask
const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
const client = createClient({ chain: testnetBradbury, account: accounts[0] });
await client.connect("testnetBradbury");

// Read contract
const result = await client.readContract({
  address: CONTRACT_ADDRESS,
  functionName: "get_claim",
  args: [0],
});

// Write contract (always value: BigInt(0) — payable not supported yet)
const hash = await client.writeContract({
  address: CONTRACT_ADDRESS,
  functionName: "submit_claim",
  args: [text, category, challengePeriod],
  value: BigInt(0),
});

// Wait for finalization (AI consensus takes 3-10 min on Bradbury)
const receipt = await client.waitForTransactionReceipt({
  hash,
  status: TransactionStatus.FINALIZED,
  interval: 5_000,
  retries: 120,   // 10 minute timeout
});
```

### Important frontend notes:
- `gl.message.value` does not work as expected — always send `value: BigInt(0)`
- Pass stake amounts as method arguments instead of transaction value
- Bradbury finalization takes 3-10 minutes — set timeout accordingly
- Rate limit: don't poll more than once per 60 seconds

---

## Working Contract Template

```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json

class MyContract(gl.Contract):
    data:  TreeMap[str, str]
    count: u64
    owner: str

    def __init__(self) -> None:
        self.count = u64(0)
        self.owner = str(gl.message.sender_address)

    @gl.public.write
    def add_item(self, text: str) -> int:
        id = int(self.count)
        self.count = u64(id + 1)
        self.data[str(id)] = json.dumps({"text": text}, sort_keys=True)
        return id

    @gl.public.write
    def resolve_item(self, id: int) -> dict:
        assert str(id) in self.data, "Not found"
        item = json.loads(self.data[str(id)])

        _prompt = f"Is this statement true? {item['text']} Reply TRUE or FALSE only."

        def check():
            return gl.nondet.exec_prompt(_prompt).strip().upper()[:5]

        def validate(leader) -> bool:
            if not isinstance(leader, gl.vm.Return):
                return False
            return leader.calldata == check()

        verdict = gl.vm.run_nondet(check, validate)
        item["verdict"] = verdict
        self.data[str(id)] = json.dumps(item, sort_keys=True)
        return {"id": id, "verdict": verdict}

    @gl.public.view
    def get_item(self, id: int) -> dict:
        assert str(id) in self.data, "Not found"
        return json.loads(self.data[str(id)])
```

---

## Reference Contracts

- **FactOracle** — Full fact-checking oracle with web evidence fetching, multi-step AI pipeline, leaderboard, and payout mechanics
- **PredictionMarket** — Binary prediction market with AI resolution and confidence bonus

Both contracts deployed on Bradbury Testnet. Source code and frontend at:

https://explorer-bradbury.genlayer.com/tx/0xf7f983975ec25ca56876469ec6226c511abf31f7930af32c8cf83587a7c00298
https://explorer-bradbury.genlayer.com/tx/0xc298c6fd45fd9b45a6a82659cd8719db389d6e4abe0ce26ddf4bff26eba0fe3c
https://github.com/whatsgood200/genlayer-fact-oracle
