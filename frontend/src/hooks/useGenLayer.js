// frontend/src/hooks/useGenLayer.js
// ============================================================
// REAL genlayer-js SDK integration — no mock data
// Based on official docs: docs.genlayer.com
// ============================================================

import { useState, useCallback, useRef, useEffect } from "react";

// ── Config ─────────────────────────────────────────────────
const ORACLE_ADDRESS  = import.meta.env.VITE_ORACLE_ADDRESS  || "";
const MARKET_ADDRESS  = import.meta.env.VITE_MARKET_ADDRESS  || "";
const NETWORK_NAME    = import.meta.env.VITE_NETWORK          || "testnetBradbury";


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
      const { createClient }      = await import("genlayer-js");
      const chains                = await import("genlayer-js/chains");

      const chain = chains[NETWORK_NAME] || chains.testnetBradbury;

      if (!window.ethereum) {
        throw new Error("MetaMask not detected. Please install MetaMask.");
      }
      const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
      const walletAddress = accounts[0];

      const client = createClient({ chain, account: walletAddress });
      await client.connect(NETWORK_NAME);

      clientRef.current = client;
      setAccount(walletAddress);
      setConnected(true);

      // Stagger reads to avoid rate limiting
      await loadClaims(client);
      await new Promise(r => setTimeout(r, 500));
      await loadStats(client);
      await new Promise(r => setTimeout(r, 500));
      await loadLeaderboard(client);
    });
  }, [withLoading]);


  // ── Generic read helper ───────────────────────────────────
  const readContract = useCallback(async (client, address, functionName, args = []) => {
    return client.readContract({ address, functionName, args });
  }, []);


  // ── Generic write helper ──────────────────────────────────
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

      const receipt = await client.waitForTransactionReceipt({
        hash,
        status: TransactionStatus.FINALIZED,
        interval: 5_000,
        retries: 120,      // 120 × 5s = 10 min max
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

  // Auto-refresh every 60 seconds when connected (avoid rate limiting)
  useEffect(() => {
    if (!connected) return;
    const id = setInterval(refreshClaims, 60_000);
    return () => clearInterval(id);
  }, [connected, refreshClaims]);


  // ── Contract write actions ────────────────────────────────

  const submitClaim = useCallback(async ({ text, category, stake, challengePeriod = 20 }) => {
    return withLoading(async () => {
      const client = clientRef.current;
      if (!client) throw new Error("Not connected");
      if (!ORACLE_ADDRESS) throw new Error("VITE_ORACLE_ADDRESS not set in .env.local");

      const receipt = await writeContract(
        client,
        ORACLE_ADDRESS,
        "submit_claim",
        [text, category, challengePeriod],
        BigInt(0),  // value always zero — GenLayer doesn't support payable methods yet
      );

      await loadClaims(client);
      return receipt;
    });
  }, [withLoading, writeContract, loadClaims]);

  const challengeClaim = useCallback(async (claimId, stake) => {
    return withLoading(async () => {
      const client = clientRef.current;
      if (!client) throw new Error("Not connected");

      await writeContract(
        client,
        ORACLE_ADDRESS,
        "challenge_claim",
        [claimId],
        BigInt(0),
      );
      await loadClaims(client);
    });
  }, [withLoading, writeContract, loadClaims]);

  const resolveClaim = useCallback(async (claimId) => {
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
        BigInt(0),  // bets also zero value for now
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
    account,
    connected,
    claims,
    stats,
    leaderboard,
    loading,
    error,
    txPending,
    connect,
    clearError,
    submitClaim,
    challengeClaim,
    resolveClaim,
    claimPayout,
    refreshClaims,
    createMarket,
    placeBet,
    resolveMarket,
    getMarketOdds,
  };
}