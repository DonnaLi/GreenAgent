async function call(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep the default message */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  getWeights: () => call("/weights"),
  setWeights: (w_carbon) => call("/weights", { method: "PUT", body: JSON.stringify({ w_carbon }) }),
  listShipments: () => call("/shipments"),
  createShipment: (data) => call("/shipments", { method: "POST", body: JSON.stringify(data) }),
  approve: (id) => call(`/shipments/${id}/approve`, { method: "POST" }),
  reject: (id) => call(`/shipments/${id}/reject`, { method: "POST" }),
  stats: () => call("/stats"),
};
