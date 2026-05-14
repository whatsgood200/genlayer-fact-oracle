# How to Start — GitHub Codespaces Guide
## Complete step-by-step, zero assumptions

---

## Why Codespaces is the right choice

- Linux environment in your browser — no Docker Desktop install on Windows
- Node.js, Python, Git, and Docker all pre-installed
- Run `genlayer init` and access Studio via a forwarded URL
- Push to GitHub directly from the terminal
- Free tier: 60 hours/month on the 2-core machine (plenty for this project)
- Works on any computer including your Windows machine via Chrome

---

## PHASE 1 — Put the project on GitHub (15 minutes)

### Step 1: Create a GitHub account if you don't have one
Go to https://github.com and sign up. Use your real email.
Verify your email — GitHub requires it before you can use Codespaces.

### Step 2: Create a new repository
1. Click the "+" in the top right of GitHub
2. Click "New repository"
3. Name: `genlayer-fact-oracle`
4. Description: `AI-powered fact-checking oracle built on GenLayer Intelligent Contracts`
5. Set to PUBLIC (important for builder program visibility)
6. Do NOT check "Initialize with README" — you already have one
7. Click "Create repository"

### Step 3: Upload your project files
You have two options. Option A is easier.

**Option A — Upload via GitHub web interface (easiest):**
1. On your new empty repo page, click "uploading an existing file"
2. You need to upload files folder by folder. Start with the root files:
   - Drag and drop: README.md, WINDOWS_SETUP.md, CODESPACES_GUIDE.md, requirements.txt
3. Click "Commit changes"
4. Then click "Add file" > "Create new file" for each folder:
   - Create `contracts/fact_oracle.py` — paste the contents
   - Create `contracts/prediction_market.py` — paste the contents
   - Create `tests/test_oracle.py` — paste the contents
   - Create `tests/conftest.py` — paste the contents
   - Create `scripts/simulate_consensus.py` — paste the contents
   - Create `scripts/deploy.py` — paste the contents
   - Create `cli/demo.py` — paste the contents
   - Create `frontend/package.json` — paste the contents
   - Create `frontend/vite.config.js` — paste the contents
   - Create `frontend/index.html` — paste the contents
   - Create `frontend/src/main.jsx` — paste the contents
   - Create `frontend/src/App.jsx` — paste the contents
   - Create `frontend/src/index.css` — paste the contents
   - Create `frontend/src/hooks/useGenLayer.js` — paste the contents
   - Create `frontend/src/components/ClaimDetail.jsx` — paste the contents
   - Create `frontend/src/components/index.jsx` — paste the contents

**Option B — Use Git from Windows CMD (if you have Git installed):**
```
cd C:\Users\YourName\Desktop\genlayer-oracle
git init
git add .
git commit -m "feat: FactOracle AI fact-checking oracle for GenLayer"
git branch -M main
git remote add origin https://github.com/YOURUSERNAME/genlayer-fact-oracle.git
git push -u origin main
```
If it asks for credentials, use your GitHub username and a Personal Access Token
(not your password). Create one at: GitHub → Settings → Developer Settings →
Personal Access Tokens → Generate new token (classic) → check "repo" scope.

### Step 4: Verify your repo looks right
Go to https://github.com/YOURUSERNAME/genlayer-fact-oracle
You should see the README displayed with the architecture diagrams.
If you see a file list with no README preview, check that README.md is in the root.

---

## PHASE 2 — Open in GitHub Codespaces (10 minutes)

### Step 5: Launch a Codespace
1. On your repo page, click the green "Code" button
2. Click the "Codespaces" tab
3. Click "Create codespace on main"
4. Wait 1-2 minutes. A VS Code editor opens in your browser.
   This is a full Linux machine running in the cloud.

### Step 6: Verify the environment
In the Codespaces terminal (bottom of the screen), run:
```bash
node --version     # should be v18 or higher
python3 --version  # should be 3.11 or higher
docker --version   # should be 20+ — this is pre-installed in Codespaces
git --version      # should be 2.x
```
If any of these fail, run `sudo apt-get install -y nodejs python3 docker.io`

---

## PHASE 3 — Install GenLayer and start local node (30-60 minutes)

### Step 7: Install the GenLayer CLI
```bash
npm install -g genlayer
genlayer --version
```

### Step 8: Start Docker (required by genlayer init)
Docker is installed but the daemon may not be running. Start it:
```bash
sudo dockerd &
sleep 5
docker info
```
If `docker info` shows "Server:" info — Docker is running.

If you get "permission denied", run:
```bash
sudo chmod 666 /var/run/docker.sock
```
Then try `docker info` again.

### Step 9: Initialize GenLayer local node
```bash
genlayer init --numValidators 5
```
This downloads Docker images (~2GB). On Codespaces this takes 5-15 minutes.
Do NOT close the terminal while it downloads.

When prompted to select an LLM provider, choose:
- "openai" if you have an OpenAI API key
- "heurist" for free credits (no API key needed — recommended)

When it says "Studio available at http://localhost:8080" — it is ready.

### Step 10: Access GenLayer Studio
In Codespaces, ports are automatically forwarded.
Look at the bottom of VS Code for "PORTS" tab.
You'll see port 8080 listed with a forwarded URL like:
https://your-codespace-name-8080.app.github.dev

Click that URL. GenLayer Studio opens in a new browser tab.

If you don't see it in the PORTS tab:
1. Click the PORTS tab
2. Click "Add Port"
3. Type 8080
4. Right-click the port row and select "Open in Browser"

---

## PHASE 4 — Test contract in Studio (1-2 hours)

### Step 11: Load your contract into Studio
1. In Studio, click the "+" button in the left sidebar (Your Contracts)
2. Name it "FactOracle"
3. Open the file `contracts/fact_oracle.py` in the Codespaces editor (left panel)
4. Select all (Ctrl+A), copy (Ctrl+C)
5. Paste into the Studio editor
6. Click Save

### Step 12: Deploy locally
1. Click the "Run and Deploy" tab in Studio
2. No constructor parameters needed
3. Click "Deploy"
4. Watch the Logs panel at the bottom

SUCCESS looks like: a contract address appears, e.g. `0xABCDEF123...`
FAILURE will show a red error message — read it carefully.

### Step 13: Most common errors and exact fixes

**Error: "TreeMap is not defined"**
Fix: Make sure the first line after the comment is `from genlayer import *`
NOT `import gl` or `import genlayer`

**Error: "gl.nondet called outside of nondet block"**
Fix: You have a gl.nondet call directly in a method body.
It MUST be inside an inner function like:
```python
def fetch():
    return gl.nondet.web.render(url)
result = gl.eq_principle.strict_eq(fetch)
```

**Error: "name 'self' is not defined" inside inner function**
Fix: You referenced self inside a nondet inner function.
Capture the value you need BEFORE the inner function:
```python
# WRONG:
def fetch():
    return gl.nondet.web.render(self.some_url)  # self not available here

# RIGHT:
url = self.some_url  # capture before inner function
def fetch():
    return gl.nondet.web.render(url)  # use captured variable
```

**Error: "Contract not found" when calling methods**
Fix: You're using the wrong address. Copy the address from the Deploy output exactly.

### Step 14: Test submit_claim
1. Click "Execute Transactions" tab in Studio
2. Select method: `submit_claim`
3. Fill parameters:
   - text: "The speed of light in a vacuum is approximately 299,792 km/s."
   - category: "science"
   - challenge_blocks: 20
4. Set value: 1000000
5. Click Execute
6. Wait ~10 seconds
7. You should see the claim_id (0) returned in the logs

### Step 15: Test resolve_claim
1. Select method: `resolve_claim`
2. Parameter: claim_id = 0
3. Click Execute
4. This takes 1-3 MINUTES — validators are fetching web pages and running AI
5. You will see validator logs showing each one working
6. When done, select `get_claim` with claim_id = 0
7. You should see a verdict: TRUE, FALSE, UNCERTAIN, or INVALID

SCREENSHOT THIS. It is your proof of work.

---

## PHASE 5 — Deploy to Bradbury Testnet (1 hour)

### Step 16: Get a MetaMask wallet
Install MetaMask extension in Chrome: https://metamask.io
Create a new wallet. WRITE DOWN the 12-word seed phrase on paper.
Copy your wallet address (it starts with 0x...)

### Step 17: Get testnet tokens
Go to: https://faucet.genlayer.com
Connect MetaMask. Click "Request tokens".
Wait 2-3 minutes. You need these for gas fees.

### Step 18: Switch GenLayer CLI to testnet
In Codespaces terminal:
```bash
genlayer network set testnet-bradbury
genlayer network info
# Should show: network: testnet-bradbury
```

### Step 19: Import your wallet into GenLayer CLI
```bash
genlayer account import
# It will ask for your private key
# In MetaMask: click three dots > Account Details > Show private key
# Enter it when prompted
# Set a password when asked (anything you'll remember)
```

### Step 20: Deploy FactOracle to Bradbury
```bash
genlayer deploy contracts/fact_oracle.py
```
Wait 1-2 minutes. When done you see:
```
✓ Contract deployed: 0xYOUR_ORACLE_ADDRESS
✓ Transaction hash: 0xABC...
```
COPY THE CONTRACT ADDRESS. Put it somewhere safe.

### Step 21: Deploy PredictionMarket
```bash
genlayer deploy contracts/prediction_market.py
```
Copy that address too.

### Step 22: Submit a real live claim on testnet
```bash
genlayer write 0xYOUR_ORACLE_ADDRESS submit_claim \
  '"The speed of light in vacuum is approximately 299792 km per second."' \
  '"science"' \
  20 \
  --value 1000000
```
Wait for the transaction hash.

### Step 23: Resolve the claim on testnet
```bash
genlayer write 0xYOUR_ORACLE_ADDRESS resolve_claim 0
```
This takes 2-5 minutes on testnet. Real validators are running real AI.

### Step 24: Read the result
```bash
genlayer call 0xYOUR_ORACLE_ADDRESS get_claim 0
```
You should see the full claim with verdict, confidence, and reasoning.

SCREENSHOT EVERYTHING. Terminal output, contract address, tx hash.
These are your submission evidence.

---

## PHASE 6 — Wire up the frontend (1-2 hours)

### Step 25: Create .env.local
In the Codespaces terminal:
```bash
cd frontend
cp .env.example .env.local 2>/dev/null || touch .env.local
```
Open .env.local in the editor and paste:
```
VITE_ORACLE_ADDRESS=0xYOUR_ORACLE_ADDRESS_FROM_STEP_20
VITE_MARKET_ADDRESS=0xYOUR_MARKET_ADDRESS_FROM_STEP_21
VITE_NETWORK=testnetBradbury
```

### Step 26: Install dependencies
```bash
cd frontend
npm install
# This installs React, Vite, AND genlayer-js (the real SDK)
```

### Step 27: Start the frontend dev server
```bash
npm run dev
```
Codespaces will show port 3000 in the PORTS tab.
Open it in browser. You should see the FactOracle UI.

### Step 28: Connect MetaMask to the dApp
1. Click "Connect Wallet" in the UI
2. MetaMask pops up — approve the connection
3. The SDK calls client.connect("testnetBradbury")
4. MetaMask may ask you to add the GenLayer Bradbury network — approve it
5. Your address should appear in the header

### Step 29: Test a real transaction from the UI
1. Click "Submit Claim"
2. Enter a claim, pick a category, set stake to 1000000
3. Click Submit
4. MetaMask pops up asking to approve the transaction — approve it
5. Wait for the transaction to finalize (shows loading spinner)
6. The claim should appear in the list with status PENDING

### Step 30: Test resolve from the UI
1. Click your claim in the list
2. Click "Resolve Claim"
3. MetaMask asks to approve — approve it
4. Wait 2-5 minutes (AI consensus running)
5. The claim updates to RESOLVED with a real AI verdict

---

## PHASE 7 — Push everything and submit (1 hour)

### Step 31: Commit and push from Codespaces
```bash
cd /workspaces/genlayer-fact-oracle
git add .
git commit -m "feat: add real genlayer-js SDK integration and testnet deployment"
git push
```

### Step 32: Check your GitHub repo
Go to https://github.com/YOURUSERNAME/genlayer-fact-oracle
Verify the README renders correctly with the Mermaid diagrams.
Check that all files are there.

### Step 33: Submit to the builder portal
Go to: https://portal.genlayer.foundation
Connect the same wallet you deployed with.
Click "Submit Contribution".
Fill in:
- Type: Builder / dApp
- Title: FactOracle — AI Fact-Checking & Prediction Oracle
- Description: [describe what you built, 2-3 sentences]
- GitHub URL: https://github.com/YOURUSERNAME/genlayer-fact-oracle
- Contract addresses: your deployed addresses on Bradbury
- Evidence: screenshot of live resolve_claim output

---

## Common Codespaces issues

**Codespace goes to sleep:**
Codespaces sleep after 30 minutes of inactivity.
Go to github.com/codespaces, click your codespace, click "Resume".
Your terminal state is lost but files are saved.
After resuming: run `sudo dockerd &` and `genlayer up` to restart the local node.

**Out of free hours:**
Free tier is 60 hours/month. If you run out:
- All your file changes are saved in the repo (you pushed them)
- You only need the Codespace for the local Studio testing
- For testnet deployment you just need Node.js locally — use Windows CMD

**Port 8080 not showing up:**
Click PORTS tab, click the + button, type 8080, press Enter.
Then right-click and select "Open in Browser".

**genlayer init fails with Docker error:**
Run: `sudo service docker start`
Wait 10 seconds, then try `genlayer init` again.
