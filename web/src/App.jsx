import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const money = (n) =>
  n == null ? "—" : n.toLocaleString("en-CA", { style: "currency", currency: "CAD" });
const kg = (n) => (n == null ? "—" : `${n.toLocaleString("en-CA", { maximumFractionDigits: 1 })} kg`);
const day = (iso) =>
  iso ? new Date(iso).toLocaleDateString("en-CA", { month: "short", day: "numeric" }) : "—";

function inDays(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

const STATUS_LABEL = {
  pending: "Waiting for approval",
  approved: "Approved",
  rejected: "Rejected",
  no_bids: "No valid bids",
};

function Balance({ carbonPct, onChange }) {
  const costPct = 100 - carbonPct;
  return (
    <div className="balance">
      <div className="balance-head">
        <span className="cost">Cost {costPct}%</span>
        <span className="carbon">Carbon {carbonPct}%</span>
      </div>
      <div className="balance-bar" aria-hidden="true">
        <div className="seg cost-fill" style={{ width: `${costPct}%` }} />
        <div className="seg carbon-fill" style={{ width: `${carbonPct}%` }} />
      </div>
      <input
        type="range"
        min="0"
        max="100"
        step="5"
        value={carbonPct}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label="Weight given to carbon versus cost"
      />
      <p className="hint">Applies to the next request. Carriers keep running.</p>
    </div>
  );
}

function ScoreBar({ bid, wCarbon }) {
  if (bid.score == null) return <span className="muted">Not scored</span>;
  const cost = (1 - wCarbon) * bid.norm_price * 100;
  const carbon = wCarbon * bid.norm_co2e * 100;
  return (
    <div className="score" title={`Score ${bid.score.toFixed(2)} (lower is better)`}>
      <div className="score-track">
        <div className="seg cost-fill" style={{ width: `${cost}%` }} />
        <div className="seg carbon-fill" style={{ width: `${carbon}%` }} />
      </div>
      <span className="score-num">{bid.score.toFixed(2)}</span>
    </div>
  );
}

function Recommendation({ shipment, onDecide, busy }) {
  const top = shipment.bids.find((b) => b.carrier_id === shipment.recommended_carrier);
  const pending = shipment.status === "pending";
  return (
    <section className="result" aria-live="polite">
      <p className="route">
        {shipment.origin} to {shipment.destination}, {shipment.weight_kg.toLocaleString()} kg, due{" "}
        {day(shipment.deadline)}
      </p>
      {top ? (
        <>
          <h2>{top.carrier_name}</h2>
          <p className="facts">
            {top.mode} · {money(top.price)} · arrives {day(top.eta)} · {kg(top.co2e_kg)} CO2e
          </p>
          {shipment.co2e_saved_kg > 0 && (
            <p className="saved">{kg(shipment.co2e_saved_kg)} less CO2e than the cheapest bid</p>
          )}
        </>
      ) : (
        <h2>No carrier can take this shipment</h2>
      )}

      <blockquote className="why">
        {shipment.rationale}
        <cite>
          {shipment.rationale_source === "llm" ? "Written by AI from the bids below" : "Written from the bids below"}
        </cite>
      </blockquote>

      <table className="bids">
        <thead>
          <tr>
            <th scope="col">Carrier</th>
            <th scope="col" className="num">Price</th>
            <th scope="col">Arrives</th>
            <th scope="col" className="num">CO2e</th>
            <th scope="col">Score</th>
          </tr>
        </thead>
        <tbody>
          {shipment.bids.map((b) => (
            <tr key={b.carrier_id} className={b.rank == null ? "excluded" : b.rank === 1 ? "top" : ""}>
              <td>
                <strong>{b.carrier_name}</strong>
                <span className="sub">{b.excluded_reason ?? b.mode}</span>
              </td>
              <td className="num">{money(b.price)}</td>
              <td>{day(b.eta)}</td>
              <td className="num">{kg(b.co2e_kg)}</td>
              <td>
                <ScoreBar bid={b} wCarbon={shipment.w_carbon} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="legend">
        Shorter bar is better. <span className="key cost-key" /> cost share{" "}
        <span className="key carbon-key" /> carbon share, scored at{" "}
        {Math.round((1 - shipment.w_carbon) * 100)}% cost / {Math.round(shipment.w_carbon * 100)}% carbon.
      </p>

      {pending && top ? (
        <div className="actions">
          <button className="primary" disabled={busy} onClick={() => onDecide("approve")}>
            Approve {top.carrier_name}
          </button>
          <button disabled={busy} onClick={() => onDecide("reject")}>
            Reject
          </button>
        </div>
      ) : (
        <p className={`status status-${shipment.status}`}>{STATUS_LABEL[shipment.status]}</p>
      )}
    </section>
  );
}

export default function App() {
  const [carbonPct, setCarbonPct] = useState(50);
  const [form, setForm] = useState({ origin: "", destination: "", weight_kg: "", deadline: inDays(7) });
  const [current, setCurrent] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loaded = useRef(false);

  async function refresh() {
    const [h, s] = await Promise.all([api.listShipments(), api.stats()]);
    setHistory(h);
    setStats(s);
  }

  useEffect(() => {
    Promise.all([api.getWeights(), refresh()])
      .then(([w]) => setCarbonPct(Math.round(w.w_carbon * 100)))
      .catch(() => setError("Can't reach the API. Start it with: uvicorn api.main:app --reload"))
      .finally(() => (loaded.current = true));
  }, []);

  // Save the weighting shortly after the slider stops moving.
  useEffect(() => {
    if (!loaded.current) return;
    const t = setTimeout(() => api.setWeights(carbonPct / 100).catch((e) => setError(e.message)), 400);
    return () => clearTimeout(t);
  }, [carbonPct]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.setWeights(carbonPct / 100);
      const s = await api.createShipment({ ...form, weight_kg: Number(form.weight_kg) });
      setCurrent(s);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function decide(action) {
    setBusy(true);
    setError("");
    try {
      setCurrent(await api[action](current.id));
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const field = (name) => ({
    value: form[name],
    onChange: (e) => setForm({ ...form, [name]: e.target.value }),
  });

  return (
    <div className="page">
      <header>
        <h1>Green-Agent</h1>
        {stats && (
          <p className="total">
            {kg(stats.co2e_saved_kg)} CO2e saved across {stats.approved} approved{" "}
            {stats.approved === 1 ? "shipment" : "shipments"}
          </p>
        )}
      </header>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <main>
        <form className="request" onSubmit={submit}>
          <h2>New shipment</h2>
          <label>
            From
            <input required placeholder="Vancouver, BC" {...field("origin")} />
          </label>
          <label>
            To
            <input required placeholder="Calgary, AB" {...field("destination")} />
          </label>
          <div className="row">
            <label>
              Weight (kg)
              <input required type="number" min="1" max="40000" placeholder="2000" {...field("weight_kg")} />
            </label>
            <label>
              Deliver by
              <input required type="date" min={inDays(0)} {...field("deadline")} />
            </label>
          </div>
          <h3>How to choose</h3>
          <Balance carbonPct={carbonPct} onChange={setCarbonPct} />
          <button className="primary wide" disabled={busy}>
            {busy && !current ? "Collecting bids…" : "Get bids"}
          </button>
        </form>

        {current ? (
          <Recommendation shipment={current} onDecide={decide} busy={busy} />
        ) : (
          <section className="result empty">
            <h2>Send a shipment to compare carriers</h2>
            <p>
              Three carriers will bid on price, delivery date, and emissions. You'll see their bids ranked by your
              cost and carbon weighting, with the reasoning behind the top pick.
            </p>
          </section>
        )}
      </main>

      {history.length > 0 && (
        <section className="history">
          <h2>Shipments</h2>
          <table>
            <thead>
              <tr>
                <th scope="col">Requested</th>
                <th scope="col">Route</th>
                <th scope="col">Carrier</th>
                <th scope="col" className="num">CO2e saved</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {history.map((s) => {
                const top = s.bids.find((b) => b.carrier_id === s.recommended_carrier);
                return (
                  <tr key={s.id} onClick={() => setCurrent(s)} tabIndex={0}
                      onKeyDown={(e) => e.key === "Enter" && setCurrent(s)}>
                    <td>{day(s.created_at)}</td>
                    <td>{s.origin} to {s.destination}</td>
                    <td>{top?.carrier_name ?? "—"}</td>
                    <td className="num">{kg(s.co2e_saved_kg)}</td>
                    <td><span className={`status status-${s.status}`}>{STATUS_LABEL[s.status]}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
