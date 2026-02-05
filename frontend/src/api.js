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
