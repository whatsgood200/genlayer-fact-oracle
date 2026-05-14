// frontend/src/hooks/useGenLayer.js
// ============================================================
// REAL genlayer-js SDK integration — no mock data
// Based on official docs: docs.genlayer.com
// ============================================================
// SDK pattern:
//   import { createClient } from "genlayer-js"
//   import { testnetBradbury } from "genlayer-js/chains"
//   import { TransactionStatus } from "genlayer-js/types"
//
//   READ:  client.readContract({ address, functionName, args })
//   WRITE: const hash = await client.writeContract({ address, functionName, args, value })
//          await client.waitForTransactionReceipt({ hash, status: TransactionStatus.FINALIZED })
//   METAMASK: createClient({ chain, account: walletAddress })
//             await client.connect("testnetBradbury")  ← must call before any write
// ============================================================

import { useState, useCallback, useRef, useEffect } from "react";

// ── Config ─────────────────────────────────────────────────
// Set these in frontend/.env.local after deploying your contracts:
//   VITE_ORACLE_ADDRESS=0x...
//   VITE_MARKET_ADDRESS=0x...
//   VITE_NETWORK=testnetBradbury
const ORACLE_ADDRESS  = import.meta.env.VITE_ORACLE_ADDRESS  || "";
const MARKET_ADDRESS  = import.meta.env.VITE_MARKET_ADDRESS  || "";
const NETWORK_NAME    = import.meta.env.VITE_NETWORK          || "testnetBradbury";

// Minimum stake matching the contract constant
const MIN_STAKE_WEI = BigInt(1_000_000);


export function useGenLayer() {
  const [account,     setAccount]     = useState(null);
  const [connected,   setConnected]   = useState(false);
  const [claims,      setClaims]      = useState([]);
  const [stats,       setStats]       = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);
  const [txPending,   setTxPending]   = useState(false);

  const clientRef = useRef(null);

  // ── Error helpers ─────────────────────────────────────────
  const clearError = useCallback(() => setError(null), []);

  const handleError = useCallback((err, context = "") => {
    console.error(`[GenLayer ${context}]`, err);
    const msg = err?.message || String(err);
    // Make common errors human-readable
    if (msg.includes("user rejected"))       setError("Transaction cancelled by wallet.");
    else if (msg.includes("insufficient"))   setError("Insufficient balance. Get testnet tokens at faucet.genlayer.com");
    else if (msg.includes("Contract not"))   setError("Contract not found. Check your .env.local addresses.");
    else if (msg.includes("wrong chain"))    setError("Wrong network. Please switch MetaMask to GenLayer Bradbury.");
    else setError(`${context}: ${msg.slice(0, 140)}`);
  }, []);

  const withLoading = useCallback(async (fn) => {
    setLoading(true);
    clearError();
    try {
      return await fn();
    } catch (e) {
      handleError(e, "");
      throw e;
    } finally {
      setLoading(false);
    }
  }, [clearError, handleError]);


  // ── Connect wallet (MetaMask) ─────────────────────────────
  const connect = useCallback(async () => {
    return withLoading(async () => {
      // Dynamically import the SDK so Vite tree-shakes correctly
      const { createClient }    = await import("genlayer-js");
      const chains              = await import("genlayer-js/chains");
      const { TransactionStatus } = await import("genlayer-js/types");

      // Pick the chain object matching the env variable
      const chain = chains[NETWORK_NAME] || chains.testnetBradbury;

      // Request MetaMask accounts
      if (!window.ethereum) {
        throw new Error("MetaMask not detected. Please install MetaMask.");
      }
      const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
      const walletAddress = accounts[0];

      // Create genlayer-js client using the connected wallet address
      // The SDK uses MetaMask as the signer automatically when you pass
      // a wallet address (not a private key)
      const client = createClient({
        chain,
        account: walletAddress,
      });

      // Switch MetaMask to the correct GenLayer network
      // This throws if the wallet rejects the network switch
      await client.connect(NETWORK_NAME);

      // Store refs
      clientRef.current = client;
      setAccount(walletAddress);
      setConnected(true);

      // Load initial data
      await Promise.all([
        loadClaims(client),
        loadStats(client),
        loadLeaderboard(client),
      ]);
    });
  }, [withLoading]);


  // ── Generic read helper ───────────────────────────────────
  const readContract = useCallback(async (client, address, functionName, args = []) => {
    return client.readContract({ address, functionName, args });
  }, []);


  // ── Generic write helper ──────────────────────────────────
  // Sends tx, waits for FINALIZED, returns receipt
  const writeContract = useCallback(async (
    client, address, functionName, args = [], valueWei = BigInt(0)
  ) => {
    const { TransactionStatus } = await import("genlayer-js/types");

    setTxPending(true);
    try {
      const hash = await client.writeContract({
        address,
        functionName,
        args,
        value: valueWei,
      });

      // Wait up to 3 minutes for finalization
      // resolve_claim can take 1-3 min (validators are fetching web + running AI)
      const receipt = await client.waitForTransactionReceipt({
        hash,
        status: TransactionStatus.FINALIZED,
        interval: 4_000,   // poll every 4 seconds
        retries: 45,       // 45 × 4s = 3 min max
      });

      return receipt;
    } finally {
      setTxPending(false);
    }
  }, []);


  // ── Data loaders ──────────────────────────────────────────
  const loadClaims = useCallback(async (client) => {
    try {
      const cl = client || clientRef.current;
      if (!cl || !ORACLE_ADDRESS) return;
      const result = await readContract(cl, ORACLE_ADDRESS, "get_all_claims", []);
      // result is an array of claim dicts returned by the contract
      setClaims(Array.isArray(result) ? result : []);
    } catch (e) {
      handleError(e, "loadClaims");
    }
  }, [readContract, handleError]);

  const loadStats = useCallback(async (client) => {
    try {
      const cl = client || clientRef.current;
      if (!cl || !ORACLE_ADDRESS) return;
      const result = await readContract(cl, ORACLE_ADDRESS, "get_stats", []);
      setStats(result || null);
    } catch (e) {
      handleError(e, "loadStats");
    }
  }, [readContract, handleError]);

  const loadLeaderboard = useCallback(async (client) => {
    try {
      const cl = client || clientRef.current;
      if (!cl || !ORACLE_ADDRESS) return;
      const result = await readContract(cl, ORACLE_ADDRESS, "get_leaderboard", []);
      setLeaderboard(Array.isArray(result) ? result : []);
    } catch (e) {
      handleError(e, "loadLeaderboard");
    }
  }, [readContract, handleError]);

  const refreshClaims = useCallback(async () => {
    if (!clientRef.current) return;
    await Promise.all([
      loadClaims(clientRef.current),
      loadStats(clientRef.current),
    ]);
  }, [loadClaims, loadStats]);

  // Auto-refresh every 15 seconds when connected
  useEffect(() => {
    if (!connected) return;
    const id = setInterval(refreshClaims, 15_000);
    return () => clearInterval(id);
  }, [connected, refreshClaims]);


  // ── Contract write actions ────────────────────────────────

  const submitClaim = useCallback(async ({ text, category, stake, challengePeriod = 20 }) => {
    return withLoading(async () => {
      const client = clientRef.current;
      if (!client) throw new Error("Not connected");
      if (!ORACLE_ADDRESS) throw new Error("VITE_ORACLE_ADDRESS not set in .env.local");

      // stake is passed as number (e.g. 1000000), convert to BigInt wei
      const stakeWei = BigInt(stake);
      if (stakeWei < MIN_STAKE_WEI) {
        throw new Error(`Minimum stake is ${MIN_STAKE_WEI.toString()} wei`);
      }

      const receipt = await writeContract(
        client,
        ORACLE_ADDRESS,
        "submit_claim",
        [text, category, challengePeriod],
        stakeWei,
      );

      // The contract returns the new claim_id as the result
      // Refresh to get updated state
      await loadClaims(client);
      return receipt;
    });
  }, [withLoading, writeContract, loadClaims]);

  const challengeClaim = useCallback(async (claimId, stake) => {
    return withLoading(async () => {
      const client = clientRef.current;
      if (!client) throw new Error("Not connected");

      const stakeWei = BigInt(stake);
      await writeContract(
        client,
        ORACLE_ADDRESS,
        "challenge_claim",
        [claimId],
        stakeWei,
      );
      await loadClaims(client);
    });
  }, [withLoading, writeContract, loadClaims]);

  const resolveClaim = useCallback(async (claimId) => {
    // NOTE: resolve_claim triggers AI consensus — validators fetch web data
    // and run AI reasoning. This takes 1-3 minutes on testnet.
    // The txPending state will be true the entire time.
    return withLoading(async () => {
      const client = clientRef.current;
      if (!client) throw new Error("Not connected");

      const receipt = await writeContract(
        client,
        ORACLE_ADDRESS,
        "resolve_claim",
        [claimId],
        BigInt(0),
      );
      await loadClaims(client);
      return receipt;
    });
  }, [withLoading, writeContract, loadClaims]);

  const claimPayout = useCallback(async (claimId) => {
    return withLoading(async () => {
      const client = clientRef.current;
      if (!client) throw new Error("Not connected");

      const receipt = await writeContract(
        client,
        ORACLE_ADDRESS,
        "claim_payout",
        [claimId],
        BigInt(0),
      );
      await loadClaims(client);
      return receipt;
    });
  }, [withLoading, writeContract, loadClaims]);


  // ── Prediction Market actions ─────────────────────────────

  const createMarket = useCallback(async ({
    question, description, resolutionHint, category, durationBlocks = 100
  }) => {
    return withLoading(async () => {
      const client = clientRef.current;
      if (!client) throw new Error("Not connected");
      if (!MARKET_ADDRESS) throw new Error("VITE_MARKET_ADDRESS not set in .env.local");

      await writeContract(
        client,
        MARKET_ADDRESS,
        "create_market",
        [question, description, resolutionHint, category, durationBlocks],
        BigInt(0),
      );
    });
  }, [withLoading, writeContract]);

  const placeBet = useCallback(async (marketId, position, betAmount) => {
    return withLoading(async () => {
      const client = clientRef.current;
      if (!client) throw new Error("Not connected");

      await writeContract(
        client,
        MARKET_ADDRESS,
        "place_bet",
        [marketId, position],
        BigInt(betAmount),
      );
    });
  }, [withLoading, writeContract]);

  const resolveMarket = useCallback(async (marketId) => {
    return withLoading(async () => {
      const client = clientRef.current;
      if (!client) throw new Error("Not connected");

      await writeContract(
        client,
        MARKET_ADDRESS,
        "resolve_market",
        [marketId],
        BigInt(0),
      );
    });
  }, [withLoading, writeContract]);

  const getMarketOdds = useCallback(async (marketId) => {
    try {
      const client = clientRef.current;
      if (!client || !MARKET_ADDRESS) return null;
      return await readContract(client, MARKET_ADDRESS, "get_market_odds", [marketId]);
    } catch (e) {
      handleError(e, "getMarketOdds");
      return null;
    }
  }, [readContract, handleError]);


  return {
    // State
    account,
    connected,
    claims,
    stats,
    leaderboard,
    loading,
    error,
    txPending,

    // Wallet
    connect,
    clearError,

    // Oracle actions
    submitClaim,
    challengeClaim,
    resolveClaim,
    claimPayout,
    refreshClaims,

    // Market actions
    createMarket,
    placeBet,
    resolveMarket,
    getMarketOdds,
  };
}
