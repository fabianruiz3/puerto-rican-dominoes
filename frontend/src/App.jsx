import React, { useState, useEffect } from "react";
import { startMatch, playMove, passTurn } from "./api";

// Puerto Rican flag colors for theming
const COLORS = {
  redPR: "#ed1c24",
  bluePR: "#0054a5",
  white: "#ffffff",
  dark: "#0a0f14",
  darkGreen: "#0d3320",
  feltGreen: "#1a4d33",
  gold: "#f4d03f",
  lightText: "#e8e8e8",
  mutedText: "#9ca3af",
};

function tileImgSrc(t) {
  return `/dominoes/${t.a}-${t.b}.png`;
}

// CSS styles as a constant
const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    background: linear-gradient(135deg, ${COLORS.dark} 0%, #0d1f17 50%, ${COLORS.dark} 100%);
    min-height: 100vh;
  }

  .app-container {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    min-height: 100vh;
    padding: 24px;
    max-width: 1400px;
    margin: 0 auto;
  }

  .header {
    text-align: center;
    margin-bottom: 32px;
  }

  .title {
    font-family: 'Libre Baskerville', Georgia, serif;
    font-size: 2.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, ${COLORS.gold} 0%, #fff8dc 50%, ${COLORS.gold} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 8px 0;
    text-shadow: 0 4px 20px rgba(244, 208, 63, 0.3);
    letter-spacing: 1px;
  }

  .subtitle {
    color: ${COLORS.mutedText};
    font-size: 1rem;
    font-weight: 400;
    margin: 0;
  }

  .flag-accent {
    display: flex;
    justify-content: center;
    gap: 4px;
    margin-top: 12px;
  }

  .flag-stripe {
    width: 40px;
    height: 4px;
    border-radius: 2px;
  }

  .start-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 60vh;
    gap: 32px;
  }

  .mode-section {
    text-align: center;
  }

  .mode-title {
    color: ${COLORS.lightText};
    font-size: 1.1rem;
    margin-bottom: 16px;
    font-weight: 500;
  }

  .button-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    max-width: 500px;
  }

  .start-btn {
    background: linear-gradient(135deg, ${COLORS.feltGreen} 0%, ${COLORS.darkGreen} 100%);
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px 32px;
    color: ${COLORS.lightText};
    font-family: inherit;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .start-btn:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
    border-color: ${COLORS.gold};
  }

  .start-btn:active {
    transform: translateY(-2px);
  }

  .start-btn .points {
    font-size: 2rem;
    font-weight: 700;
    color: ${COLORS.gold};
  }

  .start-btn .mode-label {
    font-size: 0.85rem;
    color: ${COLORS.mutedText};
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .game-grid {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 24px;
    animation: fadeIn 0.5s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .main-area {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .table-area {
    background: radial-gradient(ellipse at center, ${COLORS.feltGreen} 0%, ${COLORS.darkGreen} 100%);
    border-radius: 24px;
    padding: 24px;
    min-height: 320px;
    border: 4px solid #0f2a1a;
    box-shadow: 
      inset 0 4px 30px rgba(0, 0, 0, 0.3),
      0 8px 32px rgba(0, 0, 0, 0.4);
    position: relative;
    overflow: hidden;
  }

  .table-area::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
    pointer-events: none;
    opacity: 0.5;
  }

  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    position: relative;
    z-index: 1;
  }

  .table-title {
    font-size: 0.9rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: rgba(255, 255, 255, 0.6);
  }

  .turn-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 20px;
    font-size: 0.85rem;
    color: ${COLORS.lightText};
  }

  .turn-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    animation: pulse 1.5s infinite;
  }

  .turn-dot.your-turn {
    background: #4ade80;
  }

  .turn-dot.waiting {
    background: ${COLORS.gold};
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(1.1); }
  }

  .layout-container {
    display: flex;
    flex-direction: column;
    gap: 6px;
    align-items: center;
    justify-content: center;
    min-height: 200px;
    position: relative;
    z-index: 1;
  }

  .tile-row {
    display: flex;
    gap: 4px;
    justify-content: center;
  }

  .table-tile {
    height: 70px;
    width: auto;
    border-radius: 8px;
    box-shadow: 
      0 4px 8px rgba(0, 0, 0, 0.4),
      0 2px 4px rgba(0, 0, 0, 0.3);
    transition: transform 0.3s ease;
  }

  .table-tile:hover {
    transform: scale(1.05);
  }

  .empty-table {
    color: rgba(255, 255, 255, 0.4);
    font-size: 1rem;
    text-align: center;
    padding: 48px;
  }

  .pass-section {
    display: flex;
    justify-content: center;
    margin-top: 16px;
    position: relative;
    z-index: 1;
  }

  .pass-btn {
    background: rgba(0, 0, 0, 0.4);
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    padding: 12px 32px;
    color: ${COLORS.lightText};
    font-family: inherit;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .pass-btn:hover:not(:disabled) {
    background: rgba(237, 28, 36, 0.3);
    border-color: ${COLORS.redPR};
  }

  .pass-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .hand-area {
    background: linear-gradient(180deg, rgba(15, 30, 22, 0.9) 0%, rgba(10, 20, 15, 0.95) 100%);
    border-radius: 20px;
    padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .hand-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .hand-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: ${COLORS.lightText};
  }

  .tile-count {
    background: rgba(255, 255, 255, 0.1);
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.85rem;
    color: ${COLORS.mutedText};
  }

  .hand-tiles {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    justify-content: center;
  }

  .hand-tile-btn {
    background: linear-gradient(145deg, #243d2e, #1a2e22);
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
  }

  .hand-tile-btn::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
    transition: left 0.5s ease;
  }

  .hand-tile-btn:hover:not(:disabled)::before {
    left: 100%;
  }

  .hand-tile-btn:hover:not(:disabled) {
    transform: translateY(-6px) scale(1.02);
    border-color: ${COLORS.gold};
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4);
  }

  .hand-tile-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .hand-tile-btn.selected {
    border-color: ${COLORS.gold};
    box-shadow: 0 0 20px rgba(244, 208, 63, 0.3);
  }

  .hand-tile-img {
    height: 80px;
    width: auto;
    display: block;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .empty-hand {
    color: ${COLORS.mutedText};
    text-align: center;
    padding: 24px;
    font-style: italic;
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .panel {
    background: linear-gradient(180deg, rgba(15, 30, 22, 0.95) 0%, rgba(10, 20, 15, 0.98) 100%);
    border-radius: 20px;
    padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .panel-title {
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: ${COLORS.mutedText};
    margin-bottom: 20px;
  }

  .team-score {
    margin-bottom: 20px;
  }

  .team-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .team-name {
    font-weight: 600;
    color: ${COLORS.lightText};
    font-size: 0.95rem;
  }

  .team-points {
    font-weight: 700;
    font-size: 1.5rem;
  }

  .team-a .team-points {
    color: #4ade80;
  }

  .team-b .team-points {
    color: #60a5fa;
  }

  .progress-bar {
    height: 8px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
  }

  .progress-fill.team-a {
    background: linear-gradient(90deg, #22c55e, #4ade80);
  }

  .progress-fill.team-b {
    background: linear-gradient(90deg, #3b82f6, #60a5fa);
  }

  .player-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .player-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 12px;
    transition: background 0.2s ease;
  }

  .player-item:hover {
    background: rgba(255, 255, 255, 0.06);
  }

  .player-item.current {
    background: rgba(74, 222, 128, 0.1);
    border: 1px solid rgba(74, 222, 128, 0.3);
  }

  .player-info {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .player-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 0.85rem;
    color: #fff;
  }

  .player-avatar.p0 { background: #22c55e; }
  .player-avatar.p1 { background: #3b82f6; }
  .player-avatar.p2 { background: #22c55e; opacity: 0.7; }
  .player-avatar.p3 { background: #3b82f6; opacity: 0.7; }

  .player-name {
    font-weight: 500;
    color: ${COLORS.lightText};
    font-size: 0.9rem;
  }

  .player-tag {
    font-size: 0.75rem;
    color: ${COLORS.mutedText};
    background: rgba(255, 255, 255, 0.08);
    padding: 2px 8px;
    border-radius: 4px;
    margin-left: 6px;
  }

  .player-score {
    font-weight: 700;
    color: ${COLORS.gold};
    font-size: 1.1rem;
  }

  .game-info {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
  }

  .info-label {
    color: ${COLORS.mutedText};
  }

  .info-value {
    color: ${COLORS.lightText};
    font-weight: 500;
  }

  .end-selector {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    animation: fadeIn 0.2s ease;
  }

  .end-selector-content {
    background: linear-gradient(180deg, #1a3326, #0f2118);
    border-radius: 24px;
    padding: 32px;
    border: 2px solid rgba(255, 255, 255, 0.1);
    text-align: center;
    max-width: 400px;
  }

  .end-selector-title {
    font-size: 1.2rem;
    color: ${COLORS.lightText};
    margin-bottom: 8px;
  }

  .end-selector-subtitle {
    color: ${COLORS.mutedText};
    font-size: 0.9rem;
    margin-bottom: 24px;
  }

  .end-buttons {
    display: flex;
    gap: 16px;
    justify-content: center;
  }

  .end-btn {
    background: linear-gradient(135deg, ${COLORS.feltGreen}, ${COLORS.darkGreen});
    border: 2px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    padding: 16px 32px;
    color: ${COLORS.lightText};
    font-family: inherit;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .end-btn:hover {
    transform: scale(1.05);
    border-color: ${COLORS.gold};
  }

  .cancel-btn {
    background: transparent;
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    padding: 12px 24px;
    color: ${COLORS.mutedText};
    font-family: inherit;
    font-size: 0.9rem;
    cursor: pointer;
    margin-top: 16px;
    transition: all 0.2s ease;
  }

  .cancel-btn:hover {
    border-color: ${COLORS.redPR};
    color: ${COLORS.redPR};
  }

  .loading-overlay {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: rgba(0, 0, 0, 0.8);
    padding: 12px 24px;
    border-radius: 12px;
    color: ${COLORS.lightText};
    display: flex;
    align-items: center;
    gap: 12px;
    z-index: 50;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: ${COLORS.gold};
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .new-game-btn {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    padding: 8px 16px;
    color: ${COLORS.mutedText};
    font-family: inherit;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .new-game-btn:hover {
    border-color: ${COLORS.redPR};
    color: ${COLORS.redPR};
  }

  @media (max-width: 900px) {
    .game-grid {
      grid-template-columns: 1fr;
    }
    
    .sidebar {
      flex-direction: row;
      flex-wrap: wrap;
    }
    
    .panel {
      flex: 1;
      min-width: 280px;
    }
  }
`;

function chunkLayout(layout, perRow) {
  const rows = [];
  for (let i = 0; i < layout.length; i += perRow) {
    rows.push(layout.slice(i, i + perRow));
  }
  return rows;
}

function App() {
  const [gameId, setGameId] = useState(null);
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedTile, setSelectedTile] = useState(null);

  useEffect(() => {
    const styleEl = document.createElement("style");
    styleEl.textContent = styles;
    document.head.appendChild(styleEl);
    return () => document.head.removeChild(styleEl);
  }, []);

  async function handleStart(targetPoints, mode) {
    setLoading(true);
    try {
      const data = await startMatch(targetPoints, mode);
      setGameId(data.gameId);
      setState(data.state);
    } finally {
      setLoading(false);
    }
  }

  async function handlePlay(tileIndex, end) {
    if (!gameId) return;
    setLoading(true);
    setSelectedTile(null);
    try {
      const data = await playMove(gameId, tileIndex, end);
      setState(data.state);
    } finally {
      setLoading(false);
    }
  }

  async function handlePass() {
    if (!gameId) return;
    setLoading(true);
    try {
      const data = await passTurn(gameId);
      setState(data.state);
    } finally {
      setLoading(false);
    }
  }

  function handleTileClick(idx) {
    if (!state || state.hand_state.current_player !== 0) return;
    
    // If no tiles on table, play directly
    if (!state.hand_state.ends) {
      handlePlay(idx, "start");
      return;
    }
    
    // Check if tile can play on both ends
    const tile = state.players[0].hand[idx];
    const { left, right } = state.hand_state.ends;
    const canPlayLeft = tile.a === left || tile.b === left;
    const canPlayRight = tile.a === right || tile.b === right;
    
    if (canPlayLeft && canPlayRight && left !== right) {
      // Can play both sides - show selector
      setSelectedTile(idx);
    } else if (canPlayLeft) {
      handlePlay(idx, "left");
    } else if (canPlayRight) {
      handlePlay(idx, "right");
    } else {
      // Can't play this tile - could add feedback here
    }
  }

  function handleNewGame() {
    setGameId(null);
    setState(null);
    setSelectedTile(null);
  }

  const hand = state ? state.players[0].hand : [];
  const mode = state ? state.config.mode : "FFA";
  const target = state ? state.config.target_points : 0;
  const currentPlayer = state ? state.hand_state.current_player : -1;
  const isYourTurn = currentPlayer === 0;

  let team0Score = 0;
  let team1Score = 0;
  if (state && mode === "TEAMS") {
    team0Score = state.players[0].score + state.players[2].score;
    team1Score = state.players[1].score + state.players[3].score;
  }

  function barWidth(score) {
    if (!target || score <= 0) return "0%";
    const ratio = Math.min(score / target, 1);
    return `${ratio * 100}%`;
  }

  const layout = state ? state.hand_state.layout : [];
  const rows = chunkLayout(layout, 8);

  return (
    <div className="app-container">
      <header className="header">
        <h1 className="title">Puerto Rican Dominoes</h1>
        <p className="subtitle">La tradición boricua en tu pantalla</p>
        <div className="flag-accent">
          <div className="flag-stripe" style={{ background: COLORS.redPR }} />
          <div className="flag-stripe" style={{ background: COLORS.white }} />
          <div className="flag-stripe" style={{ background: COLORS.bluePR }} />
          <div className="flag-stripe" style={{ background: COLORS.white }} />
          <div className="flag-stripe" style={{ background: COLORS.redPR }} />
        </div>
      </header>

      {!gameId && (
        <div className="start-screen">
          <div className="mode-section">
            <div className="mode-title">Select Game Mode</div>
            <div className="button-grid">
              <button className="start-btn" onClick={() => handleStart(200, "ffa")}>
                <span className="points">200</span>
                <span className="mode-label">Free for All</span>
              </button>
              <button className="start-btn" onClick={() => handleStart(500, "ffa")}>
                <span className="points">500</span>
                <span className="mode-label">Free for All</span>
              </button>
              <button className="start-btn" onClick={() => handleStart(200, "teams")}>
                <span className="points">200</span>
                <span className="mode-label">2v2 Teams</span>
              </button>
              <button className="start-btn" onClick={() => handleStart(500, "teams")}>
                <span className="points">500</span>
                <span className="mode-label">2v2 Teams</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {state && (
        <div className="game-grid">
          <div className="main-area">
            <div className="table-area">
              <div className="table-header">
                <span className="table-title">Mesa</span>
                <div className="turn-indicator">
                  <div className={`turn-dot ${isYourTurn ? "your-turn" : "waiting"}`} />
                  <span>{isYourTurn ? "Your Turn" : `Player ${currentPlayer}'s Turn`}</span>
                </div>
              </div>
              
              <div className="layout-container">
                {rows.length > 0 ? (
                  rows.map((row, i) => {
                    const r = i % 2 === 0 ? row : [...row].reverse();
                    return (
                      <div key={i} className="tile-row">
                        {r.map((t, idx) => (
                          <img
                            key={`${i}-${idx}`}
                            src={tileImgSrc(t)}
                            alt={`${t.a}|${t.b}`}
                            className="table-tile"
                          />
                        ))}
                      </div>
                    );
                  })
                ) : (
                  <div className="empty-table">
                    {isYourTurn ? "Play the first domino!" : "Waiting for first move..."}
                  </div>
                )}
              </div>

              <div className="pass-section">
                <button
                  className="pass-btn"
                  disabled={loading || !isYourTurn || hand.length === 0}
                  onClick={handlePass}
                >
                  Pass Turn
                </button>
              </div>
            </div>

            <div className="hand-area">
              <div className="hand-header">
                <span className="hand-title">Your Hand</span>
                <span className="tile-count">{hand.length} tiles</span>
              </div>
              
              <div className="hand-tiles">
                {hand.length > 0 ? (
                  hand.map((t, idx) => (
                    <button
                      key={idx}
                      className={`hand-tile-btn ${selectedTile === idx ? "selected" : ""}`}
                      disabled={loading || !isYourTurn}
                      onClick={() => handleTileClick(idx)}
                    >
                      <img
                        src={tileImgSrc(t)}
                        alt={`${t.a}|${t.b}`}
                        className="hand-tile-img"
                      />
                    </button>
                  ))
                ) : (
                  <div className="empty-hand">You have no tiles remaining</div>
                )}
              </div>
            </div>
          </div>

          <div className="sidebar">
            <div className="panel">
              <div className="panel-title">Scores</div>
              
              {mode === "TEAMS" ? (
                <>
                  <div className="team-score team-a">
                    <div className="team-label">
                      <span className="team-name">Team A (You & P2)</span>
                      <span className="team-points">{team0Score}</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill team-a" style={{ width: barWidth(team0Score) }} />
                    </div>
                  </div>
                  
                  <div className="team-score team-b">
                    <div className="team-label">
                      <span className="team-name">Team B (P1 & P3)</span>
                      <span className="team-points">{team1Score}</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill team-b" style={{ width: barWidth(team1Score) }} />
                    </div>
                  </div>
                </>
              ) : null}

              <ul className="player-list">
                {state.players.map((p) => (
                  <li key={p.index} className={`player-item ${currentPlayer === p.index ? "current" : ""}`}>
                    <div className="player-info">
                      <div className={`player-avatar p${p.index}`}>
                        {p.index === 0 ? "👤" : `P${p.index}`}
                      </div>
                      <span className="player-name">
                        Player {p.index}
                        {p.index === 0 && <span className="player-tag">You</span>}
                        {mode === "TEAMS" && p.index === 2 && <span className="player-tag">Ally</span>}
                      </span>
                    </div>
                    <span className="player-score">{p.score}</span>
                  </li>
                ))}
              </ul>

              <div className="game-info">
                <div className="info-row">
                  <span className="info-label">Target</span>
                  <span className="info-value">{target} points</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Mode</span>
                  <span className="info-value">{mode === "TEAMS" ? "2v2 Teams" : "Free for All"}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Status</span>
                  <span className="info-value">
                    {state.hand_state.last_move_blocked ? "🔒 Blocked" : "🎮 Active"}
                  </span>
                </div>
              </div>
            </div>

            <button className="new-game-btn" onClick={handleNewGame}>
              ← New Game
            </button>
          </div>
        </div>
      )}

      {selectedTile !== null && state && (
        <div className="end-selector">
          <div className="end-selector-content">
            <div className="end-selector-title">Choose Side to Play</div>
            <div className="end-selector-subtitle">
              Left: {state.hand_state.ends.left} | Right: {state.hand_state.ends.right}
            </div>
            <div className="end-buttons">
              <button className="end-btn" onClick={() => handlePlay(selectedTile, "left")}>
                ← Left
              </button>
              <button className="end-btn" onClick={() => handlePlay(selectedTile, "right")}>
                Right →
              </button>
            </div>
            <button className="cancel-btn" onClick={() => setSelectedTile(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading && (
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Processing...</span>
        </div>
      )}
    </div>
  );
}

export default App;
