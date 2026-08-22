import React, { useState, useEffect, useRef, useCallback } from "react";
import { startMatch, playMove, passTurn, nextHand, runArena, getArenaResults, getArenaMatch, getBots } from "./api";

const C = {
  red: "#ed1c24", blue: "#0054a5", gold: "#e6c54a",
  felt: "#1a5c38", feltDark: "#10402a", feltDeep: "#0a2e1c",
  darkBg: "#0b1810", panelBorder: "rgba(255,255,255,0.07)",
  text: "#eaeaea", muted: "#8a9b8f", green: "#4ade80", blueAccent: "#60a5fa",
};

function tileImgSrc(a, b) {
  return `/dominoes/${Math.min(a, b)}-${Math.max(a, b)}.png`;
}

/* ── SNAKE LAYOUT ENGINE v6 ── */
const TW = 78, TH = 39, GAP = 2, PAD = 12;
const DBL_OVERHANG = Math.ceil((TW - TH) / 2) + 2;

function layoutArm(tiles, sx, sy, startDir, bounds, turnSeq, arm) {
  const P = [];
  let dir = startDir, tIdx = 0, vc = 0;
  const flipWhen = arm === "right" ? (t) => t.a > t.b : (t) => t.a < t.b;

  for (let i = 0; i < tiles.length; i++) {
    const t = tiles[i];
    const dbl = t.a === t.b;
    const horiz = dir === "right" || dir === "left";
    let w, h;
    if (dbl) { w = horiz ? TH : TW; h = horiz ? TW : TH; }
    else     { w = horiz ? TW : TH; h = horiz ? TH : TW; }
    const adv = dbl ? TH : TW;

    let turned = false, dblTriggeredTurn = false;
    if (i > 0 && tIdx < turnSeq.length) {
      let shouldTurn = false, dblTurn = false;
      const p = P[P.length - 1];
      if (dir === "right" && p.x + p.w + GAP + adv > bounds.right) shouldTurn = true;
      if (dir === "left"  && p.x - GAP - adv < bounds.left) shouldTurn = true;
      if (dir === "down"  && p.y + p.h + GAP + adv > bounds.bottom) shouldTurn = true;
      if (dir === "up"    && p.y - GAP - adv < bounds.top) shouldTurn = true;
      if (!horiz && dbl && vc >= 1) { dblTurn = true; shouldTurn = false; }
      if (shouldTurn) {
        dir = turnSeq[tIdx++]; vc = 0; turned = true;
        const newH = dir === "right" || dir === "left";
        if (dbl) { w = newH ? TH : TW; h = newH ? TW : TH; }
        else     { w = newH ? TW : TH; h = newH ? TH : TW; }
      }
      dblTriggeredTurn = dblTurn;
    }

    const nowHoriz = dir === "right" || dir === "left";
    if (!nowHoriz) vc++; else vc = 0;

    let x, y;
    if (i === 0) {
      if (dir === "right") { x = sx; y = sy - h / 2; }
      else if (dir === "left") { x = sx - w; y = sy - h / 2; }
      else if (dir === "down") { x = sx - w / 2; y = sy; }
      else { x = sx - w / 2; y = sy - h; }
    } else {
      const p = P[P.length - 1];
      const pcx = p.x + p.w / 2, pcy = p.y + p.h / 2;
      if (!turned) {
        if (dir === "right") { x = p.x + p.w + GAP; y = pcy - h / 2; }
        else if (dir === "left") { x = p.x - GAP - w; y = pcy - h / 2; }
        else if (dir === "down") { x = pcx - w / 2; y = p.y + p.h + GAP; }
        else { x = pcx - w / 2; y = p.y - GAP - h; }
      } else {
        if (p.dir === "right" && dir === "down") { x = p.x + p.w - TH / 2 - w / 2; y = p.y + p.h + GAP; }
        else if (p.dir === "down" && dir === "left") { x = p.x - GAP - w; y = p.y + p.h - TH / 2 - h / 2; }
        else if (p.dir === "left" && dir === "up") { x = p.x - w / 2 + TH / 2; y = p.y - GAP - h; }
        else if (p.dir === "up" && dir === "right") { x = p.x + p.w + GAP; y = p.y - h / 2 + TH / 2; }
      }
    }

    let rotation = 0, scaleX = 1;
    if (dbl) { rotation = nowHoriz ? 90 : 0; }
    else {
      if (dir === "right") rotation = 0;
      else if (dir === "down") rotation = 90;
      else if (dir === "left") rotation = 180;
      else rotation = 270;
      if (flipWhen(t)) scaleX = -1;
    }

    P.push({ tile: t, x, y, w, h, rotation, scaleX, dbl, dir });
    if (dblTriggeredTurn && tIdx < turnSeq.length) { dir = turnSeq[tIdx++]; vc = 0; }
  }
  return P;
}

function computeSnake(layout, cw, ch) {
  if (!layout || !layout.length || cw < 100 || ch < 100) return [];
  const inset = PAD + DBL_OVERHANG;
  const bounds = { left: inset, right: cw - inset, top: inset, bottom: ch - inset };
  const mid = Math.floor(layout.length / 2);
  const my = Math.floor(ch / 2), mx = Math.floor(cw / 2);
  const rp = layoutArm(layout.slice(mid), mx + GAP, my, "right", bounds, ["down", "left"], "right");
  const lt = layout.slice(0, mid).reverse();
  const lp = layoutArm(lt, mx - GAP, my, "left", bounds, ["up", "right"], "left");
  const all = new Array(layout.length);
  for (let i = 0; i < rp.length; i++) all[mid + i] = rp[i];
  for (let i = 0; i < lp.length; i++) all[mid - 1 - i] = lp[i];
  return all.filter(Boolean);
}

function DominoChain({ layout, height = 480 }) {
  const ref = useRef(null);
  const [dims, setDims] = useState({ w: 0, h: 0 });
  const measure = useCallback(() => {
    if (ref.current) { const r = ref.current.getBoundingClientRect(); setDims({ w: r.width, h: r.height }); }
  }, []);
  useEffect(() => { measure(); const ro = new ResizeObserver(measure); if (ref.current) ro.observe(ref.current); return () => ro.disconnect(); }, [measure]);
  const pos = computeSnake(layout, dims.w, dims.h);
  return (
    <div ref={ref} style={{ position: "relative", width: "100%", height, zIndex: 1 }}>
      {pos.map((p, i) => (
        <div key={i} style={{ position: "absolute", left: p.x, top: p.y, width: p.w, height: p.h, overflow: "visible" }} title={`${p.tile.a}|${p.tile.b}`}>
          <img src={tileImgSrc(p.tile.a, p.tile.b)} alt="" draggable={false}
            style={{ width: TW, height: TH, transform: `rotate(${p.rotation}deg)${p.scaleX === -1 ? " scaleX(-1)" : ""}`,
              transformOrigin: "center", position: "absolute", left: "50%", top: "50%",
              marginLeft: -TW / 2, marginTop: -TH / 2, borderRadius: 4, boxShadow: "0 2px 5px rgba(0,0,0,.45)" }} />
        </div>
      ))}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   ARENA MODE — Bot vs Bot with replay
   ══════════════════════════════════════════════════════════ */

function ArenaMode({ onBack }) {
  const [botAFile, setBotAFile] = useState(null);
  const [botBFile, setBotBFile] = useState(null);
  const [numMatches, setNumMatches] = useState(1000);
  const [targetPts, setTargetPts] = useState(200);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [fullResults, setFullResults] = useState(null);
  const [replayMatch, setReplayMatch] = useState(null);
  const [replayStep, setReplayStep] = useState(0);
  const [replayHand, setReplayHand] = useState(0);

  async function handleRun() {
    if (!botAFile || !botBFile) { setError("Upload both bot files"); return; }
    setRunning(true); setProgress("Running arena..."); setError(null); setSummary(null); setFullResults(null);
    try {
      const res = await runArena(botAFile, botBFile, numMatches, targetPts);
      setSummary(res);
      setProgress("Loading match details...");
      const full = await getArenaResults(res.arena_id);
      setFullResults(full);
      setProgress("");
    } catch (e) {
      setError(e.message);
      setProgress("");
    } finally {
      setRunning(false);
    }
  }

  function openReplay(matchIdx) {
    if (!fullResults || matchIdx >= fullResults.matches.length) return;
    setReplayMatch(fullResults.matches[matchIdx]);
    setReplayHand(0);
    setReplayStep(0);
  }

  // Build replay state from moves
  function buildReplayState(match, handIdx, step) {
    if (!match || handIdx >= match.hands.length) return null;
    const hand = match.hands[handIdx];
    // Reconstruct board state at given step
    const hands = hand.starting_hands.map(h => h.map(([a, b]) => ({ a, b })));
    const layout = [];
    let ends = null;

    for (let i = 0; i < Math.min(step, hand.moves.length); i++) {
      const m = hand.moves[i];
      if (m.end === "pass") continue;
      const tile = { a: m.tile[0], b: m.tile[1] };

      // Remove from hand
      const ph = hands[m.player];
      const idx = ph.findIndex(t => t.a === tile.a && t.b === tile.b);
      if (idx >= 0) ph.splice(idx, 1);

      // Place on board
      if (!ends) {
        layout.push(tile);
        ends = { left: tile.a, right: tile.b };
      } else if (m.end === "left") {
        if (tile.a === ends.left) {
          layout.unshift({ a: tile.b, b: tile.a });
          ends = { ...ends, left: tile.b };
        } else {
          layout.unshift(tile);
          ends = { ...ends, left: tile.a };
        }
      } else if (m.end === "right") {
        if (tile.a === ends.right) {
          layout.push(tile);
          ends = { ...ends, right: tile.b };
        } else {
          layout.push({ a: tile.b, b: tile.a });
          ends = { ...ends, right: tile.a };
        }
      } else if (m.end === "start") {
        layout.push(tile);
        ends = { left: tile.a, right: tile.b };
      }
    }

    const curMove = step < hand.moves.length ? hand.moves[step] : null;
    return { hands, layout, ends, currentMove: curMove, totalMoves: hand.moves.length, step };
  }

  const rs = replayMatch ? buildReplayState(replayMatch, replayHand, replayStep) : null;

  return (
    <div>
      {/* Back button */}
      <button className="new-btn" onClick={onBack} style={{ marginBottom: 16 }}>← Back to Menu</button>

      {!replayMatch && !summary && (
        <div className="panel" style={{ maxWidth: 900, margin: "0 auto" }}>
            <div className="panel-title">Bot Arena</div>
          <p style={{ color: C.muted, fontSize: ".85rem", marginBottom: 16 }}>
            Upload two Python bot files. Each bot plays as a team (players 0+2 vs 1+3) for {numMatches} matches.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ fontSize: ".8rem", color: C.muted, display: "block", marginBottom: 4 }}>Bot A (Team 0+2)</label>
              <input type="file" accept=".py" onChange={e => setBotAFile(e.target.files[0])}
                style={{ color: C.text, fontSize: ".85rem" }} />
              {botAFile && <span style={{ color: C.green, fontSize: ".8rem", marginLeft: 8 }}>{botAFile.name}</span>}
            </div>
            <div>
              <label style={{ fontSize: ".8rem", color: C.muted, display: "block", marginBottom: 4 }}>Bot B (Team 1+3)</label>
              <input type="file" accept=".py" onChange={e => setBotBFile(e.target.files[0])}
                style={{ color: C.text, fontSize: ".85rem" }} />
              {botBFile && <span style={{ color: C.green, fontSize: ".8rem", marginLeft: 8 }}>{botBFile.name}</span>}
            </div>
            <div style={{ display: "flex", gap: 16 }}>
              <div>
                <label style={{ fontSize: ".8rem", color: C.muted, display: "block", marginBottom: 4 }}>Matches</label>
                <input type="number" value={numMatches} onChange={e => setNumMatches(+e.target.value)}
                  style={{ width: 100, padding: "6px 10px", borderRadius: 8, border: `1px solid ${C.panelBorder}`, background: "rgba(0,0,0,.3)", color: C.text, fontSize: ".9rem" }} />
              </div>
              <div>
                <label style={{ fontSize: ".8rem", color: C.muted, display: "block", marginBottom: 4 }}>Target Points</label>
                <input type="number" value={targetPts} onChange={e => setTargetPts(+e.target.value)}
                  style={{ width: 100, padding: "6px 10px", borderRadius: 8, border: `1px solid ${C.panelBorder}`, background: "rgba(0,0,0,.3)", color: C.text, fontSize: ".9rem" }} />
              </div>
            </div>
            <button className="end-btn" onClick={handleRun} disabled={running} style={{ marginTop: 8 }}>
              {running ? "Running..." : "Run Arena"}
            </button>
          </div>

          {progress && <div style={{ color: C.gold, marginTop: 12, fontSize: ".85rem" }}>{progress}</div>}
          {error && <div style={{ color: C.red, marginTop: 12, fontSize: ".85rem" }}>Error: {error}</div>}

          <div style={{ marginTop: 20, padding: "14px 0", borderTop: `1px solid ${C.panelBorder}` }}>
            <div style={{ fontSize: ".78rem", color: C.muted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>Bot API</div>
            <pre style={{ background: "rgba(0,0,0,.4)", padding: 14, borderRadius: 10, fontSize: ".78rem", color: C.green, overflowX: "auto", lineHeight: 1.6 }}>{`from dominoes.bots import BotBase
from dominoes.rules import legal_moves_for_hand

class MyBot(BotBase):
    def choose_move(self, hand, ends, context=None):
        legal = legal_moves_for_hand(hand, ends)
        if not legal:
            return None
        # hand: List[Domino]          — each has .a, .b, .pips(), .is_double()
        # ends: (left_val, right_val) — or None if board is empty
        # legal: List[(Domino, "left"|"right"|"start")]
        # context (for CFR/advanced bots):
        #   context.board          — List[Domino] tiles on the board
        #   context.player_id      — which seat this bot occupies (0-3)
        #   context.hand_counts    — List[int] tiles remaining per player
        #   context.pass_counts    — List[int] consecutive passes per player
        #   context.move_history   — List[Move] full hand history
        return legal[0]  # your logic here`}</pre>
          </div>
        </div>
      )}

      {/* Results dashboard */}
      {summary && !replayMatch && (
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
          {/* Bot score cards — full width row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <div style={{ background: "rgba(74,222,128,.08)", borderRadius: 16, padding: "24px 20px", textAlign: "center", border: "2px solid rgba(74,222,128,.2)" }}>
              <div style={{ fontSize: ".72rem", color: C.muted, textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 8 }}>{summary.bot_a_name}</div>
              <div style={{ fontSize: "3.5rem", fontWeight: 800, color: C.green, lineHeight: 1 }}>{summary.team_a_wins}</div>
              <div style={{ fontSize: ".9rem", color: C.muted, marginTop: 6 }}>wins ({summary.team_a_win_pct}%)</div>
            </div>
            <div style={{ background: "rgba(96,165,250,.08)", borderRadius: 16, padding: "24px 20px", textAlign: "center", border: "2px solid rgba(96,165,250,.2)" }}>
              <div style={{ fontSize: ".72rem", color: C.muted, textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 8 }}>{summary.bot_b_name}</div>
              <div style={{ fontSize: "3.5rem", fontWeight: 800, color: C.blueAccent, lineHeight: 1 }}>{summary.team_b_wins}</div>
              <div style={{ fontSize: ".9rem", color: C.muted, marginTop: 6 }}>wins ({summary.team_b_win_pct}%)</div>
            </div>
          </div>

          {/* Stats grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 10, marginBottom: 16 }}>
            {[
              ["Matches", summary.num_matches],
              ["Time", `${summary.elapsed_seconds}s`],
              ["Avg Hands/Match", summary.avg_hands_per_match],
              ["Avg Pts A", summary.avg_points_a],
              ["Avg Pts B", summary.avg_points_b],
              ["Blocked %", `${summary.blocked_pct}%`],
            ].map(([k, v]) => (
              <div key={k} style={{ background: "rgba(255,255,255,.04)", borderRadius: 10, padding: "12px 14px" }}>
                <div style={{ fontSize: ".65rem", color: C.muted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>{k}</div>
                <div style={{ fontSize: "1.15rem", fontWeight: 700 }}>{v}</div>
              </div>
            ))}
          </div>

          {/* A bot that never actually runs -- a wrongly named class, a
              crash inside choose_move -- otherwise scores like a normal loss.
              Say so instead. */}
          {(summary.bot_a_bad_returns > 0 || summary.bot_b_bad_returns > 0) && (
            <div style={{ background: "rgba(245,158,11,.12)", border: "1px solid rgba(245,158,11,.35)", borderRadius: 10, padding: "10px 14px", marginBottom: 16, fontSize: ".82rem", color: "#fbbf24" }}>
              {summary.bot_a_bad_returns > 0 && <div>{summary.bot_a_name} returned something that was not a legal move {summary.bot_a_bad_returns.toLocaleString()} times — the arena played its first legal move instead.</div>}
              {summary.bot_b_bad_returns > 0 && <div>{summary.bot_b_name} returned something that was not a legal move {summary.bot_b_bad_returns.toLocaleString()} times — the arena played its first legal move instead.</div>}
            </div>
          )}

          {/* Win pct bar */}
          <div style={{ height: 32, borderRadius: 10, overflow: "hidden", display: "flex", marginBottom: 16 }}>
            <div style={{ width: `${summary.team_a_win_pct}%`, background: "linear-gradient(90deg, #16a34a, #4ade80)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: ".8rem", fontWeight: 700, color: "#000", minWidth: 40, transition: "width .8s ease" }}>
              {summary.team_a_win_pct}%
            </div>
            <div style={{ flex: 1, background: "linear-gradient(90deg, #2563eb, #60a5fa)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: ".8rem", fontWeight: 700, color: "#000", minWidth: 40 }}>
              {summary.team_b_win_pct}%
            </div>
          </div>

          {/* Match list for replay */}
          {fullResults && (
            <div className="panel" style={{ marginBottom: 16 }}>
              <div className="panel-title">Match Replays ({fullResults.total_matches_stored} available)</div>
              <div style={{ maxHeight: 400, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
                {fullResults.matches.map((m, i) => (
                  <button key={i} onClick={() => openReplay(i)} style={{
                    background: "rgba(255,255,255,.03)", border: "1px solid rgba(255,255,255,.06)",
                    borderRadius: 8, padding: "8px 14px", cursor: "pointer", display: "flex",
                    justifyContent: "space-between", alignItems: "center", color: C.text, fontFamily: "inherit",
                    transition: "background .15s",
                  }}
                    onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,.08)"}
                    onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,.03)"}>
                    <span style={{ fontSize: ".85rem" }}>Match #{i + 1}</span>
                    <span style={{ display: "flex", gap: 12, alignItems: "center" }}>
                      <span style={{ fontSize: ".8rem", color: C.muted }}>{m.num_hands ?? m.hands?.length ?? "?"} hands</span>
                      <span style={{ fontSize: ".8rem", color: C.green }}>{(m.final_scores[0] ?? 0) + (m.final_scores[2] ?? 0)}</span>
                      <span style={{ fontSize: ".7rem", color: C.muted }}>vs</span>
                      <span style={{ fontSize: ".8rem", color: C.blueAccent }}>{(m.final_scores[1] ?? 0) + (m.final_scores[3] ?? 0)}</span>
                      <span style={{
                        fontSize: ".7rem", fontWeight: 600, padding: "2px 8px", borderRadius: 4,
                        background: m.winner_team === 0 ? "rgba(74,222,128,.15)" : "rgba(96,165,250,.15)",
                        color: m.winner_team === 0 ? C.green : C.blueAccent,
                      }}>{m.winner_team === 0 ? "A" : "B"}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <button className="end-btn" onClick={() => { setSummary(null); setFullResults(null); }} style={{ width: "100%" }}>
            Run New Arena
          </button>
        </div>
      )}

      {/* Replay viewer */}
      {replayMatch && rs && (
        <div>
          <button className="new-btn" onClick={() => setReplayMatch(null)} style={{ marginBottom: 12 }}>← Back to Results</button>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>
            <div>
              {/* Board */}
              <div className="table" style={{ marginBottom: 12 }}>
                <div className="table-top">
                  <span className="table-lbl">Hand {replayHand + 1} / {replayMatch.hands.length}</span>
                  <span style={{ fontSize: ".8rem", color: C.muted }}>
                    Move {replayStep} / {rs.totalMoves}
                    {rs.currentMove && ` — P${rs.currentMove.player}: ${rs.currentMove.end === "pass" ? "Pass" : `${rs.currentMove.tile[0]}|${rs.currentMove.tile[1]} ${rs.currentMove.end}`}`}
                  </span>
                </div>
                {rs.layout.length > 0 ? <DominoChain layout={rs.layout} height={360} /> : <div style={{ height: 360, display: "flex", alignItems: "center", justifyContent: "center", color: "rgba(255,255,255,.3)" }}>No tiles played yet</div>}
                {rs.ends && <div className="ends-display">Left: <strong>{rs.ends.left}</strong> · Right: <strong>{rs.ends.right}</strong></div>}
              </div>

              {/* Controls */}
              <div style={{ display: "flex", gap: 8, justifyContent: "center", alignItems: "center", marginBottom: 12 }}>
                <button className="pass-btn" onClick={() => setReplayStep(0)}>⏮</button>
                <button className="pass-btn" onClick={() => setReplayStep(Math.max(0, replayStep - 1))}>◀</button>
                <span style={{ fontSize: ".85rem", minWidth: 80, textAlign: "center" }}>{replayStep} / {rs.totalMoves}</span>
                <button className="pass-btn" onClick={() => setReplayStep(Math.min(rs.totalMoves, replayStep + 1))}>▶</button>
                <button className="pass-btn" onClick={() => setReplayStep(rs.totalMoves)}>⏭</button>
              </div>

              {/* Hand selector */}
              <div style={{ display: "flex", gap: 6, justifyContent: "center", flexWrap: "wrap" }}>
                {replayMatch.hands.map((_, hi) => (
                  <button key={hi} onClick={() => { setReplayHand(hi); setReplayStep(0); }}
                    style={{
                      padding: "4px 12px", borderRadius: 6, border: "1px solid",
                      borderColor: hi === replayHand ? C.gold : "rgba(255,255,255,.1)",
                      background: hi === replayHand ? "rgba(230,197,74,.15)" : "transparent",
                      color: hi === replayHand ? C.gold : C.muted, cursor: "pointer",
                      fontSize: ".78rem", fontFamily: "inherit",
                    }}>H{hi + 1}</button>
                ))}
              </div>
            </div>

            {/* Player hands sidebar */}
            <div className="panel">
              <div className="panel-title">Player Hands</div>
              {rs.hands.map((h, pi) => (
                <div key={pi} style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: ".8rem", fontWeight: 600, color: [0, 2].includes(pi) ? C.green : C.blueAccent }}>
                      P{pi} ({[0, 2].includes(pi) ? "A" : "B"})
                    </span>
                    <span style={{ fontSize: ".75rem", color: C.muted }}>{h.length} tiles</span>
                  </div>
                  <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
                    {h.map((t, j) => (
                      <img key={j} src={tileImgSrc(t.a, t.b)} alt="" style={{ height: 24, borderRadius: 3 }} />
                    ))}
                    {h.length === 0 && <span style={{ fontSize: ".75rem", color: C.green }}>Empty</span>}
                  </div>
                </div>
              ))}

              {/* Move log */}
              <div style={{ marginTop: 12, borderTop: `1px solid ${C.panelBorder}`, paddingTop: 12 }}>
                <div className="panel-title" style={{ marginBottom: 8 }}>Move Log</div>
                <div style={{ maxHeight: 200, overflowY: "auto", fontSize: ".75rem" }}>
                  {replayMatch.hands[replayHand]?.moves.map((m, mi) => (
                    <div key={mi} style={{
                      padding: "3px 6px", borderRadius: 4, marginBottom: 2,
                      background: mi < replayStep ? "rgba(255,255,255,.04)" : "transparent",
                      color: mi < replayStep ? C.text : C.muted,
                      fontWeight: mi === replayStep - 1 ? 600 : 400,
                    }}>
                      <span style={{ color: [0, 2].includes(m.player) ? C.green : C.blueAccent }}>P{m.player}</span>
                      {" "}{m.end === "pass" ? "passed" : `${m.tile[0]}|${m.tile[1]} → ${m.end}`}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   PLAY MODE — existing human play
   ══════════════════════════════════════════════════════════ */

function PlayMode({ onBack }) {
  const [bots, setBots] = useState([]);
  const [opponent, setOpponent] = useState("greedy");
  const [partner, setPartner] = useState("greedy");
  useEffect(() => { getBots().then(setBots).catch(() => {}); }, []);
  const [gameId, setGameId] = useState(null);
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedTile, setSelectedTile] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { if (error) { const t = setTimeout(() => setError(null), 2500); return () => clearTimeout(t); } }, [error]);

  const handOver = state && state.last_hand_result;
  const matchOver = state && state.match_over;

  async function handleStart(pts, mode) {
    setLoading(true);
    try {
      const d = await startMatch(pts, mode, opponent, partner);
      setGameId(d.gameId); setState(d.state);
    }
    catch (e) { setError(e.message || "Failed to start game"); }
    finally { setLoading(false); }
  }
  async function handlePlay(ti, end) {
    if (!gameId) return; setLoading(true); setSelectedTile(null);
    try { const d = await playMove(gameId, ti, end); setState(d.state); }
    catch { setError("Invalid move"); }
    finally { setLoading(false); }
  }
  async function handlePass() {
    if (!gameId) return; setLoading(true);
    try { const d = await passTurn(gameId); setState(d.state); }
    catch { setError("Failed to pass"); }
    finally { setLoading(false); }
  }
  async function handleNextHand() {
    if (!gameId) return; setLoading(true);
    try { const d = await nextHand(gameId); setState(d.state); }
    catch { setError("Failed to start next hand"); }
    finally { setLoading(false); }
  }
  function handleTileClick(idx) {
    if (!state || state.hand_state.current_player !== 0 || handOver || matchOver) return;
    const ends = state.hand_state.ends;
    const t = state.players[0].hand[idx];
    const forced = state.hand_state.forced_tile;
    if (!ends) {
      // First hand of a match: the double-six holder has to lead the 6-6.
      if (forced && !(t.a === forced.a && t.b === forced.b)) {
        setError(`You must open with the ${forced.a}|${forced.b}`);
        return;
      }
      handlePlay(idx, "start");
      return;
    }
    const { left, right } = ends;
    const cL = t.a === left || t.b === left;
    const cR = t.a === right || t.b === right;
    if (!cL && !cR) { setError("Can't play that tile"); return; }
    if (cL && cR && left !== right) setSelectedTile(idx);
    else if (cL) handlePlay(idx, "left");
    else if (cR) handlePlay(idx, "right");
    else handlePlay(idx, "left");
  }
  function handleNewGame() { setGameId(null); setState(null); setSelectedTile(null); }

  const hand = state ? state.players[0].hand : [];
  const mode = state ? state.config.mode : "FFA";
  const target = state ? state.config.target_points : 0;
  const cp = state ? state.hand_state.current_player : -1;
  const myTurn = cp === 0 && !handOver && !matchOver;
  const layout = state ? state.hand_state.layout : [];
  const ends = state ? state.hand_state.ends : null;
  let t0 = 0, t1 = 0;
  if (state && mode === "TEAMS") { t0 = state.players[0].score; t1 = state.players[1].score; }
  const barW = s => !target || s <= 0 ? "0%" : `${Math.min(s / target, 1) * 100}%`;
  const forcedTile = state ? state.hand_state.forced_tile : null;
  const canPlay = t => {
    if (!ends) return !forcedTile || (t.a === forcedTile.a && t.b === forcedTile.b);
    return t.a === ends.left || t.b === ends.left || t.a === ends.right || t.b === ends.right;
  };
  const hasLegalMove = hand.some(canPlay);
  const hr = state ? state.last_hand_result : null;

  if (!gameId) {
    return (
      <div>
        <button className="new-btn" onClick={onBack} style={{ marginBottom: 16 }}>← Back to Menu</button>
        <div className="start" style={{ minHeight: "auto", paddingTop: 40 }}>
          <div className="start-label">Choose your table</div>

          <div className="seat-pickers">
            <div className="seat-pick">
              <label>Your partner <span className="seat-note">(seat 2)</span></label>
              <select value={partner} onChange={e => setPartner(e.target.value)}>
                {bots.map(b => (
                  <option key={b.name} value={b.name} disabled={!b.ready}>
                    {b.name}{b.ready ? "" : " (not trained)"}
                  </option>
                ))}
              </select>
            </div>
            <div className="seat-vs">vs</div>
            <div className="seat-pick">
              <label>Opponents <span className="seat-note">(seats 1 &amp; 3)</span></label>
              <select value={opponent} onChange={e => setOpponent(e.target.value)}>
                {bots.map(b => (
                  <option key={b.name} value={b.name} disabled={!b.ready}>
                    {b.name}{b.ready ? "" : " (not trained)"}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {bots.length > 0 && (
            <div className="seat-desc">
              <div><b>{partner}</b> — {bots.find(b => b.name === partner)?.description}</div>
              {partner !== opponent && (
                <div><b>{opponent}</b> — {bots.find(b => b.name === opponent)?.description}</div>
              )}
            </div>
          )}

          <div className="start-label" style={{ marginTop: 26 }}>Select game mode</div>
          <div className="start-grid">
            {[[200,"ffa"],[500,"ffa"],[200,"teams"],[500,"teams"]].map(([pts,m])=>(
              <button key={`${pts}-${m}`} className="start-btn" onClick={()=>handleStart(pts,m)}>
                <span className="pts">{pts}</span>
                <span className="lbl">{m==="ffa"?"Free for All":"2v2 Teams"}</span>
              </button>
            ))}
          </div>
          {error && <div style={{ color: C.red, marginTop: 14, fontSize: ".85rem" }}>{error}</div>}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="game">
        <div className="main">
          <div className="table">
            <div className="table-top">
              <span className="table-lbl">Table</span>
              <div className="turn-badge">
                <div className={`turn-dot ${myTurn?"on":"off"}`}/>
                <span>{matchOver?"Game Over":handOver?"Hand Over":myTurn?"Your Turn":`Player ${cp}'s Turn`}</span>
              </div>
            </div>
            {layout.length > 0 ? <DominoChain layout={layout}/> : <div className="empty-table">{myTurn?"Play the first domino!":"Waiting..."}</div>}
            {ends && (
              <div className="ends-display">
                <span className="ends-lbl">Open ends</span>
                <span className="end-chip">{ends.left}</span>
                <span className="end-chip">{ends.right}</span>
              </div>
            )}
            <div className="pass-row">
              {handOver && !matchOver && <button className="continue-btn" style={{maxWidth:200}} onClick={handleNextHand} disabled={loading}>Next Hand →</button>}
              {matchOver && <button className="continue-btn" style={{maxWidth:200}} onClick={handleNewGame}>New Game</button>}
              {!handOver && !matchOver && myTurn && !hasLegalMove &&
                <button className="pass-btn pass-live" disabled={loading} onClick={handlePass}>Pass — nothing to play</button>}
              {!handOver && !matchOver && myTurn && hasLegalMove &&
                <span className="turn-hint">Pick a tile to play</span>}
              {!handOver && !matchOver && !myTurn &&
                <span className="turn-hint">Player {cp} is thinking…</span>}
            </div>
          </div>

          {hr && (
            <div className="panel">
            <div className="panel-title">Hand Result</div>
              <div style={{textAlign:"center",marginBottom:12}}>
                <div style={{fontSize:"1rem",fontWeight:600}}>
                  {(() => {
                    const mine = mode === "TEAMS" ? (hr.winner === 0 || hr.winner === 2) : hr.winner === 0;
                    const who = hr.winner === 0 ? "You" : `Player ${hr.winner}`;
                    if (mode !== "TEAMS") return hr.blocked ? `Blocked — ${who} had the fewest pips` : `${who} went out`;
                    const side = mine ? "Your team" : "The opponents";
                    if (hr.blocked) return `Tranque — ${side} won it on pips`;
                    return `${side} won the hand (${who} went out)`;
                  })()}
                </div>
                <div className={`result-pts ${(mode === "TEAMS" ? (hr.winner === 0 || hr.winner === 2) : hr.winner === 0) ? "" : "them"}`}>
                  {(mode === "TEAMS" ? (hr.winner === 0 || hr.winner === 2) : hr.winner === 0) ? "+" : ""}
                  {hr.points_earned[hr.winner] || 0} points
                  {(mode === "TEAMS" ? (hr.winner === 0 || hr.winner === 2) : hr.winner === 0) ? "" : " to them"}
                </div>
              </div>
              <div className="result-section">
                <div className="result-label">Remaining tiles</div>
                {hr.remaining.map(p => (
                  <div key={p.index} className="result-player">
                    <div className="result-phdr">
                      <span style={{fontWeight:p.index===0?600:400}}>{p.index === 0 ? "You" : `Player ${p.index}`}</span>
                      <span className="result-pips">{p.pips} pips</span>
                    </div>
                    <div className="result-hand">
                      {p.hand.length === 0 ? <span className="result-empty">Domino!</span>
                        : p.hand.map((t, j) => <img key={j} src={tileImgSrc(t.a, t.b)} alt="" />)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="hand">
            <div className="hand-top"><span className="hand-title">Your Hand</span><span className="hand-count">{hand.length} {hand.length === 1 ? "tile" : "tiles"}</span></div>
            <div className="hand-tiles">
              {hand.length > 0 ? hand.map((t,i)=>(
                <button key={i} className={`hand-btn ${selectedTile===i?"sel":""} ${myTurn?(canPlay(t)?"ok":"no"):""}`}
                  disabled={loading||!myTurn} onClick={()=>handleTileClick(i)}>
                  <img src={tileImgSrc(t.a,t.b)} alt={`${t.a}|${t.b}`} draggable={false}/>
                </button>
              )) : <div className="hand-empty">{handOver?"Hand complete":"No tiles remaining"}</div>}
            </div>
          </div>
        </div>

        <div className="sidebar">
          <div className="panel">
            <div className="panel-title">Scores</div>
            {mode==="TEAMS"?(<>
              <div className="team-row team-a"><div className="team-hdr"><span className="team-name">Your Team</span><span className="team-pts">{t0}</span></div><div className="pbar"><div className="pfill a" style={{width:barW(t0)}}/></div></div>
              <div className="team-row team-b"><div className="team-hdr"><span className="team-name">Opponents</span><span className="team-pts">{t1}</span></div><div className="pbar"><div className="pfill b" style={{width:barW(t1)}}/></div></div>
              <div className="seats-panel">
                {state.players.map(p => {
                  const isYou = p.index === 0;
                  const isMate = p.index === 2;
                  const who = isYou ? "You" : isMate ? "Partner" : "Opponent";
                  const bot = isYou ? null : (isMate ? partner : opponent);
                  return (
                    <div key={p.index} className={`seat-row ${cp === p.index && !handOver ? "on" : ""} ${isYou || isMate ? "ours" : "theirs"}`}>
                      <span className="seat-who">{who}{bot && <span className="seat-bot">{bot}</span>}</span>
                      <span className="seat-tiles">{p.tile_count}<span className="seat-unit">{p.tile_count === 1 ? "tile" : "tiles"}</span></span>
                    </div>
                  );
                })}
              </div>
              <div className="ginfo" style={{marginTop:12}}>
                <div className="ginfo-row"><span className="ginfo-k">Target</span><span className="ginfo-v">{target} pts</span></div>
                <div className="ginfo-row"><span className="ginfo-k">On table</span><span className="ginfo-v">{layout.length} {layout.length === 1 ? "tile" : "tiles"}</span></div>
              </div>
            </>):(<>
              <ul className="plist">
                {state.players.map(p=>(
                  <li key={p.index} className={`pitem ${cp===p.index&&!handOver?"active":""}`}>
                    <div className="pinfo">
                      <div className={`pavatar p${p.index}`}>{p.index===0?"":` P${p.index}`}</div>
                      <span className="pname">Player {p.index}{p.index===0&&<span className="ptag">You</span>}</span>
                    </div>
                    <span className="pscore">{p.score}<span className="seat-unit">{p.tile_count} left</span></span>
                  </li>
                ))}
              </ul>
              <div className="ginfo">
                <div className="ginfo-row"><span className="ginfo-k">Target</span><span className="ginfo-v">{target} pts</span></div>
                <div className="ginfo-row"><span className="ginfo-k">Mode</span><span className="ginfo-v">Free for All</span></div>
                <div className="ginfo-row"><span className="ginfo-k">On Table</span><span className="ginfo-v">{layout.length}</span></div>
              </div>
            </>)}
          </div>
          <button className="new-btn" onClick={handleNewGame}>← New Game</button>
        </div>
      </div>

      {selectedTile!==null&&!handOver&&(
        <div className="modal-overlay" onClick={()=>setSelectedTile(null)}>
          <div className="modal" onClick={e=>e.stopPropagation()}>
            <h3>Choose which end</h3>
            <div className="modal-sub">This tile can play on both sides</div>
            <div className="modal-tile"><img src={tileImgSrc(hand[selectedTile].a,hand[selectedTile].b)} alt="" draggable={false}/></div>
            <div className="end-btns">
              <button className="end-btn" onClick={()=>handlePlay(selectedTile,"left")}><span className="end-val">{ends?.left}</span>← Left</button>
              <button className="end-btn" onClick={()=>handlePlay(selectedTile,"right")}><span className="end-val">{ends?.right}</span>Right →</button>
            </div>
            <button className="cancel-btn" onClick={()=>setSelectedTile(null)}>Cancel</button>
          </div>
        </div>
      )}

      {error&&<div className="toast">{error}</div>}
      {loading&&<div className="loading"><div className="spinner"/><span>{cp === 0 ? "Playing your tile…" : `Player ${cp} is playing…`}</span></div>}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   MAIN APP — Mode selector
   ══════════════════════════════════════════════════════════ */

const styles = `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@400;500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{background:${C.darkBg};min-height:100vh;font-family:'DM Sans',system-ui,sans-serif;color:${C.text}}
.app{max-width:1440px;margin:0 auto;padding:20px 24px;min-height:100vh;display:flex;flex-direction:column}
.hdr{text-align:center;margin-bottom:20px}
.hdr h1{font-family:'Playfair Display',serif;font-size:2.4rem;font-weight:900;background:linear-gradient(135deg,${C.gold},#fff8dc,${C.gold});-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:.5px}
.hdr-sub{color:${C.muted};font-size:.9rem;margin-top:2px}
.flag-bar{display:flex;justify-content:center;gap:3px;margin-top:8px}
.flag-bar span{width:32px;height:3px;border-radius:2px}
.mode-select{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;padding-bottom:14vh}
.mode-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;max-width:620px;width:100%}
.mode-btn{background:linear-gradient(145deg,${C.felt},${C.feltDark});border:2px solid rgba(255,255,255,.08);border-radius:20px;padding:32px 24px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:10px;transition:all .25s;color:${C.text};font-family:inherit;text-align:center}
.mode-btn:hover{transform:translateY(-4px);border-color:${C.gold};box-shadow:0 12px 32px rgba(0,0,0,.5)}
.mode-icon{font-size:2.4rem}
.mode-title{font-size:1.1rem;font-weight:700}
.mode-desc{font-size:.8rem;color:${C.muted};line-height:1.4}
.start{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:24px;padding-bottom:8vh}
.start-label{color:${C.muted};font-size:1rem;font-weight:500;letter-spacing:1px;text-transform:uppercase}
.start-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:420px;width:100%}
.start-btn{background:linear-gradient(145deg,${C.felt},${C.feltDark});border:2px solid rgba(255,255,255,.08);border-radius:16px;padding:20px 16px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:6px;transition:all .25s;color:${C.text};font-family:inherit}
.start-btn:hover{transform:translateY(-3px);border-color:${C.gold};box-shadow:0 8px 24px rgba(0,0,0,.5)}
.start-btn .pts{font-size:2rem;font-weight:700;color:${C.gold}}
.start-btn .lbl{font-size:.8rem;color:${C.muted};text-transform:uppercase;letter-spacing:1px}
.seat-pickers{display:flex;align-items:flex-end;gap:14px;max-width:420px;width:100%}
.seat-pick{flex:1;display:flex;flex-direction:column;gap:7px;min-width:0}
.seat-pick label{font-size:.72rem;color:${C.muted};text-transform:uppercase;letter-spacing:1.2px;font-weight:600}
.seat-note{text-transform:none;letter-spacing:0;opacity:.65;font-weight:400}
.seat-pick select{width:100%;appearance:none;background:rgba(0,0,0,.35) url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6'><path d='M0 0h10L5 6z' fill='%238a9b8f'/></svg>") no-repeat right 12px center;border:1.5px solid ${C.panelBorder};border-radius:10px;padding:10px 30px 10px 12px;color:${C.text};font-family:inherit;font-size:.9rem;cursor:pointer;transition:border-color .2s}
.seat-pick select:hover{border-color:rgba(230,197,74,.45)}
.seat-pick select:focus{outline:none;border-color:${C.gold}}
.seat-vs{color:${C.muted};font-size:.75rem;text-transform:uppercase;letter-spacing:1px;padding-bottom:11px}
.seat-desc{color:${C.muted};font-size:.76rem;max-width:460px;text-align:center;line-height:1.6;margin-top:-12px;display:flex;flex-direction:column;gap:3px}
.seat-desc b{color:${C.text};font-weight:600}
.game{display:grid;grid-template-columns:1fr 280px;gap:20px;flex:1;animation:fadeUp .4s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
.main{display:flex;flex-direction:column;gap:16px;min-width:0}
.table{background:radial-gradient(ellipse at 50% 40%,${C.felt},${C.feltDark} 70%,${C.feltDeep});border-radius:20px;padding:16px 20px;border:3px solid #0d3520;box-shadow:inset 0 2px 20px rgba(0,0,0,.35),0 6px 24px rgba(0,0,0,.4);position:relative;overflow:hidden;display:flex;flex-direction:column}
.table::before{content:'';position:absolute;inset:0;pointer-events:none;opacity:.4;background:url("data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23000' fill-opacity='.06'%3E%3Ccircle cx='20' cy='20' r='1'/%3E%3C/g%3E%3C/svg%3E")}
.table-top{display:flex;justify-content:space-between;align-items:center;position:relative;z-index:1;margin-bottom:4px}
.table-lbl{font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,.45)}
.turn-badge{display:flex;align-items:center;gap:6px;padding:5px 14px;background:rgba(0,0,0,.35);border-radius:16px;font-size:.8rem;font-weight:500}
.turn-dot{width:8px;height:8px;border-radius:50%;animation:pulse 1.4s infinite}
.turn-dot.on{background:${C.green}}.turn-dot.off{background:${C.gold}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.empty-table{height:480px;display:flex;align-items:center;justify-content:center;color:rgba(255,255,255,.35);font-size:.95rem;position:relative;z-index:1}
.ends-display{display:flex;align-items:center;justify-content:center;gap:10px;position:relative;z-index:1;margin-top:6px}
.ends-lbl{font-size:.68rem;letter-spacing:1.4px;text-transform:uppercase;color:${C.muted};font-weight:600}
.end-chip{min-width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;border-radius:9px;background:rgba(0,0,0,.4);border:1.5px solid rgba(230,197,74,.5);color:${C.gold};font-size:1.15rem;font-weight:700;font-variant-numeric:tabular-nums}
.pass-row{display:flex;justify-content:center;align-items:center;min-height:40px;margin-top:10px;position:relative;z-index:1}
.turn-hint{font-size:.82rem;color:${C.muted};letter-spacing:.3px}
.pass-btn.pass-live{border-color:rgba(230,197,74,.5);color:${C.gold}}

/* Seats. Tile counts are public at a real table -- the bots get them, so the
   player gets them too. */
.seats-panel{margin-top:14px;display:flex;flex-direction:column;gap:2px}
.seat-row{display:flex;align-items:center;justify-content:space-between;padding:7px 9px;border-radius:8px;border-left:3px solid transparent;transition:background .2s,border-color .2s}
.seat-row.ours{border-left-color:rgba(74,222,128,.45)}
.seat-row.theirs{border-left-color:rgba(96,165,250,.45)}
.seat-row.on{background:rgba(230,197,74,.10);border-left-color:${C.gold}}
.seat-who{font-size:.82rem;color:${C.text};display:flex;align-items:baseline;gap:6px}
.seat-bot{font-size:.66rem;text-transform:uppercase;letter-spacing:.8px;color:${C.muted};background:rgba(255,255,255,.06);padding:2px 5px;border-radius:4px}
.seat-tiles{font-size:.95rem;font-weight:700;color:${C.text};font-variant-numeric:tabular-nums;display:flex;align-items:baseline;gap:5px}
.seat-unit{font-size:.62rem;font-weight:500;color:${C.muted};text-transform:uppercase;letter-spacing:.6px}
.pass-btn{background:rgba(0,0,0,.4);border:1.5px solid rgba(255,255,255,.15);border-radius:10px;padding:8px 28px;color:${C.text};font-family:inherit;font-size:.85rem;font-weight:600;cursor:pointer;transition:all .2s}
.pass-btn:hover:not(:disabled){background:rgba(237,28,36,.25);border-color:${C.red}}
.pass-btn:disabled{opacity:.35;cursor:not-allowed}
.hand{background:linear-gradient(180deg,rgba(15,33,24,.92),rgba(11,24,16,.96));border-radius:16px;padding:16px 20px;border:1px solid ${C.panelBorder}}
.hand-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.hand-title{font-size:1rem;font-weight:600}
.hand-count{background:rgba(255,255,255,.08);padding:3px 10px;border-radius:10px;font-size:.8rem;color:${C.muted}}
.hand-tiles{display:flex;flex-wrap:wrap;gap:10px;justify-content:center}
.hand-btn{background:linear-gradient(145deg,#1e3a2a,#162c20);border:2px solid rgba(255,255,255,.08);border-radius:10px;padding:6px;cursor:pointer;transition:all .2s}
.hand-btn:hover:not(:disabled){transform:translateY(-5px);border-color:${C.gold};box-shadow:0 8px 20px rgba(0,0,0,.4)}
.hand-btn:disabled{opacity:.45;cursor:not-allowed}
.hand-btn.sel{border-color:${C.gold};box-shadow:0 0 16px rgba(230,197,74,.3)}
.hand-btn.ok{border-color:rgba(74,222,128,.35)}
.hand-btn.no{opacity:.55}
.hand-btn img{height:68px;width:auto;display:block;border-radius:6px}
.hand-empty{color:${C.muted};text-align:center;padding:20px;font-style:italic}
.sidebar{display:flex;flex-direction:column;gap:16px}
.panel{background:linear-gradient(180deg,rgba(15,33,24,.95),rgba(11,24,16,.98));border-radius:16px;padding:20px;border:1px solid ${C.panelBorder}}
.panel-title{font-size:.75rem;font-weight:600;text-transform:uppercase;letter-spacing:2px;color:${C.muted};margin-bottom:14px}
.team-row{margin-bottom:14px}
.team-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.team-name{font-weight:600;font-size:.9rem}
.team-pts{font-weight:700;font-size:1.3rem}
.team-a .team-pts{color:${C.green}}.team-b .team-pts{color:${C.blueAccent}}
.pbar{height:6px;background:rgba(255,255,255,.08);border-radius:3px;overflow:hidden}
.pfill{height:100%;border-radius:3px;transition:width .5s}
.pfill.a{background:linear-gradient(90deg,#22c55e,${C.green})}
.pfill.b{background:linear-gradient(90deg,#3b82f6,${C.blueAccent})}
.plist{list-style:none;display:flex;flex-direction:column;gap:6px}
.pitem{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:rgba(255,255,255,.025);border-radius:10px;transition:background .2s}
.pitem.active{background:rgba(74,222,128,.1);outline:1px solid rgba(74,222,128,.25)}
.pinfo{display:flex;align-items:center;gap:8px}
.pavatar{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:.75rem;color:#fff}
.pavatar.p0{background:#22c55e}.pavatar.p1{background:#3b82f6}
.pavatar.p2{background:#22c55e;opacity:.65}.pavatar.p3{background:#3b82f6;opacity:.65}
.pname{font-weight:500;font-size:.85rem}
.ptag{font-size:.7rem;color:${C.muted};background:rgba(255,255,255,.06);padding:2px 6px;border-radius:3px;margin-left:4px}
.pscore{font-weight:700;color:${C.gold};font-size:1rem}
.ginfo{display:flex;flex-direction:column;gap:6px;padding-top:12px;border-top:1px solid rgba(255,255,255,.06)}
.ginfo-row{display:flex;justify-content:space-between;font-size:.8rem}
.ginfo-k{color:${C.muted}}.ginfo-v{font-weight:500}
.new-btn{background:transparent;border:1px solid rgba(255,255,255,.15);border-radius:8px;padding:8px 14px;color:${C.muted};font-family:inherit;font-size:.78rem;cursor:pointer;transition:all .2s}
.new-btn:hover{border-color:${C.red};color:${C.red}}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;z-index:100;animation:fadeUp .2s ease}
.modal{background:linear-gradient(180deg,#1a3326,#0f2118);border-radius:20px;padding:28px;border:2px solid rgba(255,255,255,.1);text-align:center;max-width:420px;width:92%}
.modal h3{font-size:1.1rem;margin-bottom:6px}
.modal-sub{color:${C.muted};font-size:.85rem;margin-bottom:20px}
.modal-tile{display:flex;justify-content:center;margin-bottom:20px}
.modal-tile img{height:64px;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.4)}
.end-btns{display:flex;gap:12px;justify-content:center;margin-bottom:12px}
.end-btn{background:linear-gradient(135deg,${C.felt},${C.feltDark});border:2px solid rgba(255,255,255,.12);border-radius:12px;padding:14px 28px;color:${C.text};font-family:inherit;font-size:.95rem;font-weight:600;cursor:pointer;transition:all .2s}
.end-btn:hover{transform:scale(1.04);border-color:${C.gold}}
.end-btn .end-val{display:block;font-size:1.4rem;font-weight:700;color:${C.gold};margin-bottom:2px}
.cancel-btn{background:transparent;border:1.5px solid rgba(255,255,255,.15);border-radius:10px;padding:8px 20px;color:${C.muted};font-family:inherit;font-size:.85rem;cursor:pointer;transition:all .2s}
.cancel-btn:hover{border-color:${C.red};color:${C.red}}
.result-pts{color:${C.gold};font-size:1.1rem;font-weight:700;margin-bottom:16px}
.result-pts.them{color:${C.blueAccent}}
.result-section{text-align:left;margin-bottom:16px}
.result-label{font-size:.78rem;color:${C.muted};text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.result-player{margin-bottom:10px}
.result-phdr{display:flex;justify-content:space-between;margin-bottom:4px;font-size:.85rem}
.result-pips{color:${C.muted}}
.result-hand{display:flex;gap:4px;flex-wrap:wrap}
.result-hand img{height:28px;border-radius:3px}
.result-empty{color:${C.green};font-size:.8rem}
.continue-btn{background:linear-gradient(135deg,${C.felt},${C.feltDark});border:2px solid rgba(255,255,255,.12);border-radius:12px;padding:12px 24px;color:${C.text};font-family:inherit;font-size:.95rem;font-weight:600;cursor:pointer;transition:all .2s;width:100%;margin-top:8px}
.continue-btn:hover{border-color:${C.gold}}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:rgba(237,28,36,.9);padding:10px 24px;border-radius:10px;font-size:.85rem;font-weight:600;z-index:200;animation:fadeUp .2s ease}
.loading{position:fixed;bottom:20px;right:20px;background:rgba(0,0,0,.8);padding:10px 20px;border-radius:10px;display:flex;align-items:center;gap:10px;font-size:.85rem;z-index:50}
.spinner{width:16px;height:16px;border:2px solid rgba(255,255,255,.2);border-top-color:${C.gold};border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:900px){.game{grid-template-columns:1fr}.sidebar{flex-direction:row;flex-wrap:wrap}.panel{flex:1;min-width:240px}}
`;

function App() {
  const [mode, setMode] = useState(null); // null = menu, "play", "arena"

  useEffect(() => { const el = document.createElement("style"); el.textContent = styles; document.head.appendChild(el); return () => document.head.removeChild(el); }, []);

  return (
    <div className="app">
      <header className="hdr">
        <h1>Puerto Rican Dominoes</h1>
        <p className="hdr-sub">The classic island tradition</p>
        <div className="flag-bar">
          <span style={{background:C.red}}/><span style={{background:"#fff"}}/><span style={{background:C.blue}}/><span style={{background:"#fff"}}/><span style={{background:C.red}}/>
        </div>
      </header>

      {mode === null && (
        <div className="mode-select">
          <div className="mode-grid">
            <button className="mode-btn" onClick={() => setMode("play")}>
              <span className="mode-title">Play Game</span>
              <span className="mode-desc">Play dominoes against AI opponents</span>
            </button>
            <button className="mode-btn" onClick={() => setMode("arena")}>
              <span className="mode-title">Bot Arena</span>
              <span className="mode-desc">Upload bots to battle 1000 games with replays</span>
            </button>
          </div>
        </div>
      )}

      {mode === "play" && <PlayMode onBack={() => setMode(null)} />}
      {mode === "arena" && <ArenaMode onBack={() => setMode(null)} />}
    </div>
  );
}

export default App;