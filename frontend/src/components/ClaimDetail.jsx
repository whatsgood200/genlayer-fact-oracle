// frontend/src/components/ClaimDetail.jsx

import { useState } from "react";

const VERDICT_CONFIG = {
  TRUE:      { color: "#22c55e", bg: "rgba(34,197,94,0.1)",  label: "VERIFIED TRUE",    icon: "✓" },
  FALSE:     { color: "#ef4444", bg: "rgba(239,68,68,0.1)",  label: "VERIFIED FALSE",   icon: "✗" },
  UNCERTAIN: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)", label: "UNCERTAIN",        icon: "?" },
  INVALID:   { color: "#6366f1", bg: "rgba(99,102,241,0.1)", label: "INVALID CLAIM",    icon: "∅" },
};

export function ClaimDetail({
  claim, account, connected,
  onChallenge, onResolve, onClaimPayout, onClose,
}) {
  const [challenging,   setchallenging]   = useState(false);
  const [challengeAmt,  setChallengeAmt]  = useState("1000000");
  const [resolving,     setResolving]     = useState(false);

  const isSubmitter  = account === claim.submitter;
  const isChallenger = account === claim.challenger;
  const isPending    = claim.status === "PENDING";
  const isDisputed   = claim.status === "DISPUTED";
  const isResolved   = claim.status === "RESOLVED";

  const vc = claim.verdict ? VERDICT_CONFIG[claim.verdict] : null;

  const handleChallenge = async () => {
    setchallenging(true);
    try {
      await onChallenge(claim.id, parseInt(challengeAmt));
    } finally {
      setchallenging(false);
    }
  };

  const handleResolve = async () => {
    setResolving(true);
    try {
      await onResolve(claim.id);
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className="claim-detail">
      {/* Header */}
      <div className="detail-header">
        <div className="detail-meta">
          <span className={`status-badge status-${claim.status.toLowerCase()}`}>
            {claim.status}
          </span>
          <span className="claim-id">Claim #{claim.id}</span>
          <span className="claim-category">{claim.category.toUpperCase()}</span>
        </div>
        <button className="btn-close" onClick={onClose}>✕</button>
      </div>

      {/* Claim text */}
      <div className="detail-claim-text">
        <span className="claim-quote">"</span>
        {claim.text}
        <span className="claim-quote">"</span>
      </div>

      {/* Verdict card (if resolved) */}
      {isResolved && vc && (
        <div className="verdict-card" style={{ borderColor: vc.color, background: vc.bg }}>
          <div className="verdict-main">
            <span className="verdict-icon" style={{ color: vc.color }}>{vc.icon}</span>
            <div>
              <div className="verdict-label" style={{ color: vc.color }}>{vc.label}</div>
              {claim.confidence && (
                <div className="verdict-confidence">
                  <span>AI Confidence</span>
                  <div className="conf-bar">
                    <div
                      className="conf-fill"
                      style={{
                        width: `${claim.confidence * 100}%`,
                        background: vc.color,
                      }}
                    />
                  </div>
                  <span>{(claim.confidence * 100).toFixed(1)}%</span>
                </div>
              )}
            </div>
          </div>

          {claim.reasoning && (
            <div className="verdict-reasoning">
              <h4>AI Reasoning</h4>
              <div className="reasoning-grid">
                {claim.reasoning.key_evidence && (
                  <div className="reasoning-item">
                    <span className="ri-label">Key Evidence</span>
                    <p>{claim.reasoning.key_evidence}</p>
                  </div>
                )}
                {claim.reasoning.counterargument && (
                  <div className="reasoning-item">
                    <span className="ri-label">Counterargument</span>
                    <p>{claim.reasoning.counterargument}</p>
                  </div>
                )}
                {claim.reasoning.caveats && (
                  <div className="reasoning-item">
                    <span className="ri-label">Caveats</span>
                    <p>{claim.reasoning.caveats}</p>
                  </div>
                )}
                {claim.reasoning.source_quality && (
                  <div className="reasoning-item">
                    <span className="ri-label">Source Quality</span>
                    <p className={`sq-${claim.reasoning.source_quality.toLowerCase()}`}>
                      {claim.reasoning.source_quality}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {claim.evidence_urls?.length > 0 && (
            <div className="evidence-urls">
              <h4>Evidence Sources</h4>
              {claim.evidence_urls.map((url, i) => (
                <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                   className="evidence-link">
                  ↗ Source {i + 1}
                </a>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Stakes */}
      <div className="stakes-row">
        <div className="stake-box">
          <span className="stake-label">Submitter Stake</span>
          <span className="stake-value">{(claim.stake / 1e6).toFixed(2)}M</span>
          <span className="stake-addr">{claim.submitter?.slice(0, 10)}…</span>
        </div>
        <div className="stake-vs">VS</div>
        <div className="stake-box">
          <span className="stake-label">Challenger Stake</span>
          <span className="stake-value">
            {claim.challenger
              ? `${(claim.challenge_stake / 1e6).toFixed(2)}M`
              : "—"}
          </span>
          <span className="stake-addr">
            {claim.challenger ? `${claim.challenger.slice(0, 10)}…` : "Unchallenged"}
          </span>
        </div>
      </div>

      {/* Action area */}
      {connected && (
        <div className="action-area">
          {/* Challenge */}
          {isPending && !isSubmitter && !claim.challenger && (
            <div className="action-challenge">
              <h4>Challenge this Claim</h4>
              <p>Deposit a counter-stake to dispute this claim.</p>
              <div className="challenge-input">
                <input
                  type="number"
                  value={challengeAmt}
                  onChange={e => setChallengeAmt(e.target.value)}
                  min={claim.stake}
                  placeholder="Stake amount"
                />
                <span className="input-suffix">wei</span>
              </div>
              <button
                className="btn-danger"
                onClick={handleChallenge}
                disabled={challenging}
              >
                {challenging ? "Challenging…" : "Challenge Claim"}
              </button>
            </div>
          )}

          {/* Resolve */}
          {(isPending || isDisputed) && (
            <div className="action-resolve">
              <h4>Resolve via AI Consensus</h4>
              <p>
                Triggers multi-validator AI analysis. Each validator independently
                fetches evidence and reasons about the claim. Optimistic Democracy
                determines the final verdict.
              </p>
              <button
                className="btn-primary"
                onClick={handleResolve}
                disabled={resolving}
              >
                {resolving ? (
                  <span className="loading-text">
                    <span className="spinner" /> Running AI Consensus…
                  </span>
                ) : "Resolve Claim"}
              </button>
            </div>
          )}

          {/* Payout */}
          {isResolved && !claim.payout_claimed && (isSubmitter || isChallenger) && (
            <div className="action-payout">
              <button
                className="btn-payout"
                onClick={() => onClaimPayout(claim.id)}
              >
                Claim Payout ◇
              </button>
            </div>
          )}

          {isResolved && claim.payout_claimed && (
            <div className="payout-claimed">
              ✓ Payout already claimed
            </div>
          )}
        </div>
      )}
    </div>
  );
}
