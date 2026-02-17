const BASE_URL = "http://localhost:8000";

export async function startMatch(targetPoints = 200, mode = "ffa") {
  const res = await fetch(BASE_URL + "/api/match", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_points: targetPoints, mode })
  });
  if (!res.ok) throw new Error("Failed to start match");
  return res.json();
}

export async function playMove(gameId, tileIndex, end) {
  const res = await fetch(BASE_URL + "/api/match/" + gameId + "/play", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tile_index: tileIndex, end })
  });
  if (!res.ok) throw new Error("Failed to play move");
  return res.json();
}

export async function passTurn(gameId) {
  const res = await fetch(BASE_URL + "/api/match/" + gameId + "/pass", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  if (!res.ok) throw new Error("Failed to pass");
  return res.json();
}

export async function nextHand(gameId) {
  const res = await fetch(BASE_URL + "/api/match/" + gameId + "/next_hand", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  if (!res.ok) throw new Error("Failed to start next hand");
  return res.json();
}

export async function runArena(botAFile, botBFile, numMatches = 1000, targetPoints = 200) {
  const form = new FormData();
  form.append("bot_a", botAFile);
  form.append("bot_b", botBFile);
  form.append("num_matches", numMatches.toString());
  form.append("target_points", targetPoints.toString());
  const res = await fetch(BASE_URL + "/api/arena/run", { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Arena failed" }));
    throw new Error(err.detail || "Arena failed");
  }
  return res.json();
}

export async function getArenaResults(arenaId) {
  const res = await fetch(BASE_URL + "/api/arena/" + arenaId);
  if (!res.ok) throw new Error("Failed to get arena results");
  return res.json();
}

export async function getArenaMatch(arenaId, matchIdx) {
  const res = await fetch(BASE_URL + "/api/arena/" + arenaId + "/match/" + matchIdx);
  if (!res.ok) throw new Error("Failed to get match data");
  return res.json();
}