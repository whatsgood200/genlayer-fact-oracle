// frontend/src/components/index.jsx
import { useState, useEffect, useCallback } from "react";

// ── ClaimList ──────────────────────────────────────────────────────────────────

const STATUS_ORDER = { DISPUTED: 0, PENDING: 1, RESOLVED: 2, EXPIRED: 3 };
const VERDICT_DOT  = { TRUE: "#22c55e", FALSE: "#ef4444", UNCERTAIN: "#f59e0b", INVALID: "#6366f1" };

export function ClaimList({ claims, selected, onSelect, loading }) {
  const [filter, setFilter] = useState("ALL");
  const [search, setSearch] = useState("");

  const filtered = (claims || [])
    .filter(c => filter === "ALL" || c.status === filter)
    .filter(c => !search || c.text.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]);

  return (
    <div className="claim-list">
      <div className="list-controls">
        <input
          className="search-input"
          placeholder="Search claims…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="filter-tabs">
          {["ALL", "PENDING", "DISPUTED", "RESOLVED"].map(s => (
            <button
              key={s}
              className={`filter-btn ${filter === s ? "active" : ""}`}
              onClick={() => setFilter(s)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="list-loading">Loading…</div>}

      <div className="claim-items">
        {filtered.length === 0 && !loading && (
          <div className="list-empty">No claims found</div>
        )}
        {filtered.map(claim => (
          <button
            key={claim.id}
            className={`claim-item ${selected === claim.id ? "selected" : ""}`}
            onClick={() => onSelect(claim)}
          >
            <div className="ci-header">
              <span className={`ci-status status-${claim.status.toLowerCase()}`}>
                {claim.status}
              </span>
              {claim.verdict && (
                <span
                  className="ci-verdict-dot"
                  style={{ background: VERDICT_DOT[claim.verdict] }}
                  title={claim.verdict}
                />
              )}
              <span className="ci-id">#{claim.id}</span>
            </div>
            <p className="ci-text">{claim.text.slice(0, 80)}{claim.text.length > 80 ? "…" : ""}</p>
            <div className="ci-footer">
              <span className="ci-cat">{claim.category}</span>
              {/* FIX: stake is 0 in testing — show gracefully */}
              <span className="ci-stake">{(claim.stake / 1e6).toFixed(1)}M staked</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}


// ── StatsPanel ─────────────────────────────────────────────────────────────────

export function StatsPanel({ stats, claims }) {
  if (!stats) return <div className="panel-loading">Loading stats…</div>;

  // FIX: contract doesn't return verdict_breakdown — build it from claims array
  const vd = { TRUE: 0, FALSE: 0, UNCERTAIN: 0, INVALID: 0 };
  (claims || []).forEach(c => {
    if (c.verdict && vd[c.verdict] !== undefined) vd[c.verdict]++;
  });
  const total = vd.TRUE + vd.FALSE + vd.UNCERTAIN + vd.INVALID || 1;

  // FIX: avg_confidence is a string "0.95" — parse before math
  const avgConf = parseFloat(stats.avg_confidence || "0");

  return (
    <div className="stats-panel">
      <h2 className="panel-title">Protocol Statistics</h2>

      <div className="stats-grid">
        {/* FIX: contract returns "total" not "total_claims" */}
        <StatCard label="Total Claims"   value={stats.total ?? 0}    icon="⬡" />
        <StatCard label="Resolved"       value={stats.resolved ?? 0} icon="◎" />
        {/* FIX: parse string confidence then multiply */}
        <StatCard label="Avg Confidence" value={`${(avgConf * 100).toFixed(1)}%`} icon="◈" />
        {/* FIX: contract returns "ins_pool" not "insurance_pool" */}
        <StatCard label="Insurance Pool" value={`${((stats.ins_pool || 0) / 1e6).toFixed(2)}M`} icon="◇" />
      </div>

      <div className="verdict-chart">
        <h3>Verdict Distribution</h3>
        <div className="verdict-bars">
          {[
            ["TRUE",      vd.TRUE,      "#22c55e"],
            ["FALSE",     vd.FALSE,     "#ef4444"],
            ["UNCERTAIN", vd.UNCERTAIN, "#f59e0b"],
            ["INVALID",   vd.INVALID,   "#6366f1"],
          ].map(([label, count, color]) => (
            <div key={label} className="verdict-bar-row">
              <span className="vb-label" style={{ color }}>{label}</span>
              <div className="vb-track">
                <div
                  className="vb-fill"
                  style={{ width: `${(count / total) * 100}%`, background: color }}
                />
              </div>
              <span className="vb-count">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="recent-claims">
        <h3>Recent Activity</h3>
        <div className="activity-feed">
          {(claims || []).slice(0, 5).map(c => (
            <div key={c.id} className="activity-item">
              <span className={`status-dot status-${c.status.toLowerCase()}`} />
              <span className="ai-text">{c.text.slice(0, 60)}…</span>
              <span className="ai-cat">{c.category}</span>
            </div>
          ))}
          {(!claims || claims.length === 0) && (
            <div style={{ color: "var(--text-3)", fontSize: "13px" }}>No activity yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon }) {
  return (
    <div className="stat-card">
      <span className="sc-icon">{icon}</span>
      <span className="sc-value">{value}</span>
      <span className="sc-label">{label}</span>
    </div>
  );
}


// ── Leaderboard ────────────────────────────────────────────────────────────────

export function Leaderboard({ entries, account }) {
  return (
    <div className="leaderboard">
      <h2 className="panel-title">Fact-Checker Leaderboard</h2>
      <p className="panel-sub">Rankings by total stake won. Accuracy matters.</p>

      <div className="lb-table">
        <div className="lb-header">
          <span>#</span>
          <span>Address</span>
          <span>Correct</span>
          <span>Wrong</span>
          <span>Accuracy</span>
          <span>Stake Won</span>
        </div>

        {(entries || []).map((entry, i) => {
          const total    = (entry.correct || 0) + (entry.incorrect || 0) || 1;
          const accuracy = ((entry.correct || 0) / total * 100).toFixed(0);
          const isMe     = entry.address === account;
          // FIX: contract returns "won" not "stake_won"
          const won      = entry.won || 0;

          return (
            <div key={i} className={`lb-row ${isMe ? "lb-me" : ""} ${i < 3 ? `lb-top-${i+1}` : ""}`}>
              <span className="lb-rank">
                {i === 0 ? "◆" : i === 1 ? "◇" : i === 2 ? "○" : i + 1}
              </span>
              <span className="lb-addr">
                {isMe ? <strong>{entry.address} (you)</strong> : entry.address}
              </span>
              <span className="lb-correct">{entry.correct || 0}</span>
              <span className="lb-wrong">{entry.incorrect || 0}</span>
              <span className="lb-accuracy" style={{
                color: accuracy >= 70 ? "#22c55e" : accuracy >= 50 ? "#f59e0b" : "#ef4444"
              }}>
                {accuracy}%
              </span>
              <span className="lb-won">{(won / 1e6).toFixed(2)}M</span>
            </div>
          );
        })}

        {(!entries || entries.length === 0) && (
          <div style={{ padding: "24px", textAlign: "center", color: "var(--text-3)" }}>
            No entries yet. Submit and resolve claims to appear here.
          </div>
        )}
      </div>
    </div>
  );
}


// ── SubmitClaim Modal ──────────────────────────────────────────────────────────

export function SubmitClaim({ onSubmit, onClose, loading }) {
  const [text,            setText]            = useState("");
  const [category,        setCategory]        = useState("science");
  const [stake,           setStake]           = useState("0");
  const [challengePeriod, setChallengePeriod] = useState("20");

  const CATEGORIES = [
    "science", "politics", "economics", "sports",
    "technology", "climate", "health", "history",
  ];

  const charCount = text.length;
  const isValid   = charCount >= 10 && charCount <= 512;

  const handleSubmit = async () => {
    if (!isValid) return;
    await onSubmit({
      text,
      category,
      stake:           parseInt(stake) || 0,
      challengePeriod: parseInt(challengePeriod) || 20,
    });
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <h3>Submit a Claim</h3>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <label>Claim *</label>
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Enter a falsifiable factual claim…"
              rows={3}
              maxLength={512}
            />
            <div className={`char-count ${!isValid && charCount > 0 ? "error" : ""}`}>
              {charCount}/512
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Category</label>
              <select value={category} onChange={e => setCategory(e.target.value)}>
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Stake (wei)</label>
              {/* FIX: min="0" — contract accepts 0 stake */}
              <input
                type="number"
                value={stake}
                onChange={e => setStake(e.target.value)}
                min="0"
                placeholder="0"
              />
            </div>

            <div className="form-group">
              <label>Challenge Period (blocks)</label>
              {/* FIX: min="0" — block tracking disabled */}
              <input
                type="number"
                value={challengePeriod}
                onChange={e => setChallengePeriod(e.target.value)}
                min="0"
                max="1000"
              />
            </div>
          </div>

          <div className="submit-note">
            ⚡ AI validators will fetch real-time evidence and reach consensus via
            Optimistic Democracy. Resolution typically takes 1–3 minutes.
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            onClick={handleSubmit}
            disabled={!isValid || loading}
          >
            {loading ? "Submitting…" : "Submit Claim"}
          </button>
        </div>
      </div>
    </div>
  );
}


// ── PredictionMarket ───────────────────────────────────────────────────────────

export function PredictionMarket({ connected, account, createMarket, placeBet, resolveMarket }) {
  const [markets,    setMarkets]    = useState([]);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [betModal,   setBetModal]   = useState(null);
  const [betAmount,  setBetAmount]  = useState("0");

  const [form, setForm] = useState({
    question:       "",
    description:    "",
    resolutionHint: "",
    category:       "economics",
    durationBlocks: "100",
  });

  const loadMarkets = useCallback(async () => {
    if (!connected) return;
    setLoading(true);
    setError(null);
    try {
      const { createClient } = await import("genlayer-js");
      const chains           = await import("genlayer-js/chains");
      const MARKET_ADDRESS   = import.meta.env.VITE_MARKET_ADDRESS || "";

      if (!MARKET_ADDRESS) {
        setError("VITE_MARKET_ADDRESS not set in .env.local");
        return;
      }

      const client = createClient({ chain: chains.testnetBradbury, account });
      const result = await client.readContract({
        address:      MARKET_ADDRESS,
        functionName: "get_all_markets",
        args:         [],
      });
      setMarkets(Array.isArray(result) ? result : []);
    } catch (e) {
      setError(e.message || "Failed to load markets");
    } finally {
      setLoading(false);
    }
  }, [connected, account]);

  useEffect(() => {
    loadMarkets();
    const id = setInterval(loadMarkets, 60_000); // FIX: 60s to avoid rate limiting
    return () => clearInterval(id);
  }, [loadMarkets]);

  const handleCreateMarket = async () => {
    if (!createMarket) return;
    try {
      setLoading(true);
      await createMarket({
        question:       form.question,
        description:    form.description,
        resolutionHint: form.resolutionHint,
        category:       form.category,
        durationBlocks: parseInt(form.durationBlocks) || 100,
      });
      setShowCreate(false);
      setForm({ question:"", description:"", resolutionHint:"", category:"economics", durationBlocks:"100" });
      await loadMarkets();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePlaceBet = async () => {
    if (!betModal || !placeBet) return;
    try {
      setLoading(true);
      await placeBet(betModal.marketId, betModal.position, parseInt(betAmount) || 0);
      setBetModal(null);
      await loadMarkets();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (marketId) => {
    if (!resolveMarket) return;
    try {
      setLoading(true);
      await resolveMarket(marketId);
      await loadMarkets();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const CATEGORIES = ["economics","technology","science","politics","sports","climate","health","history"];

  return (
    <div className="prediction-market">
      <div className="pm-header">
        <h2 className="panel-title">Prediction Markets</h2>
        <div style={{ display:"flex", gap:"8px", alignItems:"center" }}>
          <button className="btn-secondary" onClick={loadMarkets} disabled={loading}>
            {loading ? "Loading…" : "↻ Refresh"}
          </button>
          <button className="btn-primary" disabled={!connected} onClick={() => setShowCreate(true)}>
            + Create Market
          </button>
        </div>
      </div>

      {!connected && (
        <div className="empty-state">
          <div className="empty-icon">◈</div>
          <h3>Connect your wallet to view markets</h3>
          <p>Prediction markets are resolved by AI consensus on the GenLayer network.</p>
        </div>
      )}

      {error && (
        <div className="error-banner" style={{ marginBottom:"16px" }}>
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {connected && !loading && markets.length === 0 && !error && (
        <div className="empty-state">
          <div className="empty-icon">◈</div>
          <h3>No markets yet</h3>
          <p>Create the first prediction market. AI validators will resolve it after the deadline.</p>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            Create First Market
          </button>
        </div>
      )}

      {markets.length > 0 && (
        <div className="markets-grid">
          {markets.map(m => {
            const total   = (m.yes_pool || 0) + (m.no_pool || 0);
            const yesProb = total ? m.yes_pool / total : 0.5;
            const noProb  = 1 - yesProb;
            // FIX: confidence is a string "0.95" — parse before math
            const conf    = parseFloat(m.confidence || "0");

            return (
              <div key={m.id} className="market-card">
                <div className="mc-header">
                  <span className={`status-badge status-${(m.status||"open").toLowerCase()}`}>
                    {m.status || "OPEN"}
                  </span>
                  <span className="mc-cat">{m.category}</span>
                  {m.outcome && (
                    <span className={`mc-outcome outcome-${m.outcome.toLowerCase()}`}>
                      {m.outcome}
                    </span>
                  )}
                </div>

                <p className="mc-question">{m.question}</p>

                <div className="mc-odds">
                  <div className="odds-bar">
                    <div className="odds-yes" style={{ width:`${yesProb*100}%` }}>
                      YES {(yesProb*100).toFixed(0)}%
                    </div>
                    <div className="odds-no" style={{ width:`${noProb*100}%` }}>
                      NO {(noProb*100).toFixed(0)}%
                    </div>
                  </div>
                </div>

                <div className="mc-footer">
                  <span>Pool: {(total/1e6).toFixed(2)}M</span>
                  {/* FIX: parse string confidence */}
                  {m.confidence != null && (
                    <span>AI Conf: {(conf * 100).toFixed(0)}%</span>
                  )}
                </div>

                {m.status === "OPEN" && connected && (
                  <div className="mc-actions">
                    <button className="btn-yes" onClick={() => setBetModal({ marketId: m.id, position:"YES" })}>
                      Bet YES
                    </button>
                    <button className="btn-no" onClick={() => setBetModal({ marketId: m.id, position:"NO" })}>
                      Bet NO
                    </button>
                    <button
                      className="btn-secondary"
                      style={{ gridColumn:"span 2", fontSize:"11px" }}
                      onClick={() => handleResolve(m.id)}
                      disabled={loading}
                    >
                      Resolve (AI)
                    </button>
                  </div>
                )}

                {m.status === "RESOLVED" && m.reasoning && (
                  <div style={{ fontSize:"11px", color:"var(--text-3)", marginTop:"8px", lineHeight:"1.5" }}>
                    {m.reasoning.text}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Create market modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={e => e.target===e.currentTarget && setShowCreate(false)}>
          <div className="modal">
            <div className="modal-header">
              <h3>Create Prediction Market</h3>
              <button className="btn-close" onClick={() => setShowCreate(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Question *</label>
                <textarea
                  rows={2}
                  value={form.question}
                  onChange={e => setForm(f=>({...f, question:e.target.value}))}
                  placeholder="Will X happen before date Y?"
                  maxLength={300}
                />
              </div>
              <div className="form-group">
                <label>Description *</label>
                <textarea
                  rows={2}
                  value={form.description}
                  onChange={e => setForm(f=>({...f, description:e.target.value}))}
                  placeholder="Explain the criteria for resolution..."
                  maxLength={500}
                />
              </div>
              <div className="form-group">
                <label>Resolution Source *</label>
                <input
                  type="text"
                  value={form.resolutionHint}
                  onChange={e => setForm(f=>({...f, resolutionHint:e.target.value}))}
                  placeholder="e.g. Official announcement at reuters.com"
                  maxLength={200}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Category</label>
                  <select value={form.category} onChange={e => setForm(f=>({...f, category:e.target.value}))}>
                    {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Duration (blocks)</label>
                  <input
                    type="number"
                    value={form.durationBlocks}
                    onChange={e => setForm(f=>({...f, durationBlocks:e.target.value}))}
                    min="10" max="10000"
                  />
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
              <button
                className="btn-primary"
                onClick={handleCreateMarket}
                disabled={loading || !form.question || !form.description || !form.resolutionHint}
              >
                {loading ? "Creating…" : "Create Market"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bet modal */}
      {betModal && (
        <div className="modal-overlay" onClick={e => e.target===e.currentTarget && setBetModal(null)}>
          <div className="modal" style={{ maxWidth:"380px" }}>
            <div className="modal-header">
              <h3>Place Bet — {betModal.position}</h3>
              <button className="btn-close" onClick={() => setBetModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Bet Amount (wei)</label>
                {/* FIX: min="0" — gl.message.value not supported */}
                <input
                  type="number"
                  value={betAmount}
                  onChange={e => setBetAmount(e.target.value)}
                  min="0"
                />
              </div>
              <p style={{ fontSize:"11px", color:"var(--text-3)" }}>
                Winnings include a +10% bonus if AI confidence ≥ 85%.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setBetModal(null)}>Cancel</button>
              <button className="btn-primary" onClick={handlePlaceBet} disabled={loading}>
                {loading ? "Placing…" : `Bet ${betModal.position}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
