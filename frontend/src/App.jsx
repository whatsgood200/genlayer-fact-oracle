// frontend/src/App.jsx
import { useState, useCallback } from "react";
import { ClaimDetail }            from "./components/ClaimDetail";
import {
  ClaimList, StatsPanel, Leaderboard,
  SubmitClaim, PredictionMarket,
}                                 from "./components/index.jsx";
import { useGenLayer }            from "./hooks/useGenLayer";
import "./index.css";

const TABS = [
  { id: "claims",  label: "Claims",            icon: "⬡" },
  { id: "market",  label: "Prediction Market",  icon: "◈" },
  { id: "stats",   label: "Stats",              icon: "◎" },
  { id: "leaders", label: "Leaderboard",        icon: "◇" },
];

export default function App() {
  const [activeTab,     setActiveTab]     = useState("claims");
  const [selectedClaim, setSelectedClaim] = useState(null);
  const [showSubmit,    setShowSubmit]    = useState(false);

  const {
    account, connected, claims, stats, leaderboard,
    loading, error, txPending,
    connect, clearError,
    submitClaim, challengeClaim, resolveClaim, claimPayout, refreshClaims,
    createMarket, placeBet, resolveMarket,
  } = useGenLayer();

  const handleClaimSelect = useCallback((claim) => {
    setSelectedClaim(claim);
    setActiveTab("claims");
  }, []);

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-mark">⬡</span>
            <div className="logo-text">
              <span className="logo-name">FactOracle</span>
              <span className="logo-sub">GenLayer · Intelligent Contracts</span>
            </div>
          </div>

          <nav className="tabs">
            {TABS.map(tab => (
              <button
                key={tab.id}
                className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
                onClick={() => { setActiveTab(tab.id); setSelectedClaim(null); }}
              >
                <span className="tab-icon">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>

          <div className="header-actions">
            {txPending && (
              <span style={{ fontSize:"11px", color:"var(--yellow)", marginRight:"12px" }}>
                <span className="spinner" style={{ marginRight:"6px" }} />
                AI consensus running…
              </span>
            )}
            {connected ? (
              <div className="wallet-info">
                <span className="wallet-dot" />
                <span className="wallet-addr">
                  {account ? `${account.slice(0,6)}…${account.slice(-4)}` : "Connected"}
                </span>
              </div>
            ) : (
              <button className="btn-connect" onClick={connect}>
                Connect Wallet
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="error-banner">
          <span>⚠ {error}</span>
          <button onClick={clearError}>✕</button>
        </div>
      )}

      {/* Main */}
      <main className="main">
        {activeTab === "claims" && (
          <div className="claims-layout">
            <div className="claims-sidebar">
              <div className="panel-header">
                <h2>Claims</h2>
                <button className="btn-primary" onClick={() => setShowSubmit(true)} disabled={!connected}>
                  + Submit Claim
                </button>
              </div>
              <ClaimList
                claims={claims}
                selected={selectedClaim?.id}
                onSelect={handleClaimSelect}
                loading={loading}
              />
            </div>
            <div className="claims-main">
              {selectedClaim ? (
                <ClaimDetail
                  claim={selectedClaim}
                  account={account}
                  connected={connected}
                  onChallenge={challengeClaim}
                  onResolve={resolveClaim}
                  onClaimPayout={claimPayout}
                  onClose={() => setSelectedClaim(null)}
                />
              ) : (
                <EmptyState onSubmit={() => setShowSubmit(true)} connected={connected} />
              )}
            </div>
          </div>
        )}

        {activeTab === "market" && (
          <PredictionMarket
            connected={connected}
            account={account}
            createMarket={createMarket}
            placeBet={placeBet}
            resolveMarket={resolveMarket}
          />
        )}

        {activeTab === "stats" && (
          <StatsPanel stats={stats} claims={claims} />
        )}

        {activeTab === "leaders" && (
          <Leaderboard entries={leaderboard} account={account} />
        )}
      </main>

      {/* Submit modal */}
      {showSubmit && (
        <SubmitClaim
          onSubmit={async (data) => {
            await submitClaim(data);
            setShowSubmit(false);
          }}
          onClose={() => setShowSubmit(false)}
          loading={loading}
        />
      )}
    </div>
  );
}

function EmptyState({ onSubmit, connected }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">⬡</div>
      <h3>Select a claim to inspect</h3>
      <p>Or submit a new claim. AI validators will fetch real evidence and reach consensus via Optimistic Democracy.</p>
      {connected
        ? <button className="btn-primary" onClick={onSubmit}>Submit Your First Claim</button>
        : <p className="empty-sub">Connect your wallet to get started.</p>
      }
      <div className="how-it-works">
        <h4>How It Works</h4>
        <div className="steps">
          {[
            ["⬡","Submit","Post a factual claim with a stake"],
            ["◈","Challenge","Others deposit a counter-stake"],
            ["◎","Resolve","AI validators fetch evidence and reach consensus"],
            ["◇","Payout","Winner collects based on AI verdict"],
          ].map(([icon,title,desc]) => (
            <div key={title} className="step">
              <span className="step-icon">{icon}</span>
              <strong>{title}</strong>
              <span>{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
