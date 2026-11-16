"use client";

import { useEffect, useMemo, useState } from "react";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL;
const PERIODS = [1, 3, 5, 10];
const cardStyle = {
  background: "#161b22",
  border: "1px solid #30363d",
  borderRadius: 14,
  padding: 18,
};

function money(value) {
  return value === null || value === undefined ? "N/A" : Number(value).toFixed(2);
}

export default function Home() {
  const [mode, setMode] = useState("compare");
  const [period, setPeriod] = useState(1);
  const [search, setSearch] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState([]);
  const [pasteList, setPasteList] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [chatQuery, setChatQuery] = useState("");
  const [chatHTML, setChatHTML] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    if (search.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const response = await fetch(
          `${BACKEND}/funds/search?q=${encodeURIComponent(search.trim())}&limit=15`,
          { signal: controller.signal }
        );
        if (!response.ok) throw new Error("Live AMFI search is temporarily unavailable.");
        const data = await response.json();
        setSuggestions(data.results || []);
      } catch (err) {
        if (err.name !== "AbortError") setError(err.message);
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [search]);

  const addFund = (name) => {
    const clean = name.trim();
    if (!clean) return;
    if (selected.some((item) => item.toLowerCase() === clean.toLowerCase())) {
      setError("That scheme is already in your selection.");
      return;
    }
    if (selected.length >= 10) {
      setError("A report can contain a maximum of 10 funds.");
      return;
    }
    setSelected((items) => [...items, clean]);
    setError("");
    setSearch("");
    setSuggestions([]);
  };

  const addPastedFunds = () => {
    const names = pasteList
      .split(/[\n;,]+/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (!names.length) return;
    const merged = [...selected];
    for (const name of names) {
      if (merged.length === 10) break;
      if (!merged.some((item) => item.toLowerCase() === name.toLowerCase())) merged.push(name);
    }
    setSelected(merged);
    setPasteList("");
    setError(merged.length < 2 ? "Add at least 2 funds to generate a comparison." : "");
  };

  const generateReport = async () => {
    if (selected.length < 2 || selected.length > 10) {
      setError("Select between 2 and 10 distinct funds.");
      return;
    }
    setLoading(true);
    setError("");
    setReport(null);
    try {
      const response = await fetch(`${BACKEND}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fund_names: selected, period }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to generate the report.");
      setReport(data);
    } catch (err) {
      setError(err.message || "Could not connect to the analysis service.");
    } finally {
      setLoading(false);
    }
  };

  const downloadPDF = async () => {
    const element = document.getElementById("comparison-report");
    if (!element || !report) return;
    const html2pdf = (await import("html2pdf.js")).default;
    await html2pdf().set({
      margin: [10, 10, 12, 10],
      filename: `Mutual_Fund_Comparison_${period}Y.pdf`,
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff" },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["css", "legacy"] },
    }).from(element).save();
  };

  const runChat = async (event) => {
    event.preventDefault();
    if (!chatQuery.trim()) return;
    setChatLoading(true);
    setChatHTML("");
    try {
      const response = await fetch(`${BACKEND}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: chatQuery, period }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Analysis failed.");
      setChatHTML(data.response || "<p>No response generated.</p>");
    } catch (err) {
      setChatHTML(`<p>${err.message}</p>`);
    } finally {
      setChatLoading(false);
    }
  };

  const generatedDate = useMemo(
    () => report?.generated_at_utc ? new Date(report.generated_at_utc).toLocaleString() : "",
    [report]
  );

  return (
    <main className="mf-shell">
      <style jsx global>{`
        body { background: #0d1117; color: #f0f6fc; }
        .mf-shell { max-width: 1120px; margin: 0 auto; padding: 38px 22px 70px; }
        .mf-hero { text-align: center; margin-bottom: 28px; }
        .mf-hero h1 { font-size: clamp(2rem, 5vw, 3.1rem); margin: 0; font-family: Outfit, sans-serif; }
        .mf-hero p { color: #8b949e; margin-top: 10px; }
        .mf-tabs { display:flex; justify-content:center; gap:10px; margin:24px 0; flex-wrap:wrap; }
        .mf-tabs button,.mf-button { border:1px solid #30363d; background:#161b22; color:#c9d1d9; padding:11px 16px; border-radius:9px; cursor:pointer; }
        .mf-tabs button.active,.mf-button.primary { background:#1f6feb; border-color:#1f6feb; color:white; }
        .mf-button:disabled { opacity:.5; cursor:not-allowed; }
        .mf-panel { background:#161b22; border:1px solid #30363d; border-radius:16px; padding:22px; margin:18px 0; }
        .mf-label { display:block; color:#c9d1d9; font-weight:600; margin-bottom:9px; }
        .mf-input,.mf-textarea,.mf-select { width:100%; padding:12px 14px; background:#0d1117; color:#f0f6fc; border:1px solid #30363d; border-radius:9px; outline:none; }
        .mf-textarea { min-height:90px; resize:vertical; }
        .mf-row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
        .mf-suggestions { margin-top:7px; border:1px solid #30363d; border-radius:10px; overflow:hidden; }
        .mf-suggestion { display:block; width:100%; text-align:left; padding:11px 13px; color:#c9d1d9; background:#0d1117; border:0; border-bottom:1px solid #30363d; cursor:pointer; }
        .mf-suggestion:hover { background:#1c2735; }
        .mf-chip { display:inline-flex; gap:8px; align-items:center; background:#1f2937; border:1px solid #3b4756; padding:7px 10px; border-radius:999px; margin:4px; font-size:13px; }
        .mf-chip button { background:none; border:0; color:#ff7b72; cursor:pointer; font-size:16px; }
        .mf-period { display:flex; gap:8px; margin:12px 0 18px; }
        .mf-period button { padding:8px 14px; border-radius:8px; border:1px solid #30363d; background:#0d1117; color:#c9d1d9; cursor:pointer; }
        .mf-period button.active { background:#1f6feb; border-color:#1f6feb; color:#fff; }
        .mf-error { color:#ff7b72; background:#3d1e23; border:1px solid #6e3038; padding:12px; border-radius:9px; margin:12px 0; }
        .mf-report { background:white; color:#172033; padding:30px; border-radius:12px; margin-top:22px; }
        .mf-report h2,.mf-report h3 { color:#14233b; }
        .mf-report p,.mf-report li { line-height:1.55; }
        .mf-report table { width:100%; border-collapse:collapse; font-size:12px; margin:12px 0 22px; }
        .mf-report th,.mf-report td { border:1px solid #dce3ec; padding:8px; text-align:left; }
        .mf-report th { background:#edf3fa; }
        .mf-report .rank-card { border:1px solid #dce3ec; border-radius:10px; padding:13px; margin:10px 0; break-inside:avoid; }
        .mf-report .muted { color:#586579; font-size:12px; }
        .mf-report .section { margin-top:26px; break-inside:avoid; }
        .mf-chat-result { background:#161b22; padding:20px; border-radius:12px; margin-top:20px; }
        @media(max-width:650px) { .mf-shell {padding:24px 13px 50px;} .mf-panel {padding:16px;} .mf-report {padding:16px;} .mf-report table {font-size:10px;} }
      `}</style>

      <header className="mf-hero">
        <h1>Mutual Fund Intelligence</h1>
        <p>Live NAV research. Transparent comparisons. AI-written reports.</p>
      </header>

      <nav className="mf-tabs">
        <button className={mode === "compare" ? "active" : ""} onClick={() => setMode("compare")}>Ranked PDF Report</button>
        <button className={mode === "assistant" ? "active" : ""} onClick={() => setMode("assistant")}>AI Assistant</button>
      </nav>

      {mode === "compare" ? (
        <>
          <section className="mf-panel">
            <h2 style={{ marginTop: 0 }}>Build a multi-fund report</h2>
            <p style={{ color: "#8b949e" }}>Choose 2–10 Indian mutual fund schemes. Search the live AMFI scheme list or paste your own list.</p>
            <label className="mf-label" htmlFor="fund-search">Search AMFI schemes</label>
            <input id="fund-search" className="mf-input" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Start typing a fund or AMC name…" />
            {searching && <p style={{ color: "#8b949e" }}>Searching live scheme master…</p>}
            {suggestions.length > 0 && (
              <div className="mf-suggestions">
                {suggestions.map((fund) => (
                  <button className="mf-suggestion" key={fund.scheme_code} onClick={() => addFund(fund.scheme_name)}>
                    <strong>{fund.scheme_name}</strong>
                    <span style={{ display: "block", color: "#8b949e", fontSize: 12 }}>Scheme {fund.scheme_code} · NAV {fund.latest_nav} · {fund.latest_date}</span>
                  </button>
                ))}
              </div>
            )}
            <div style={{ marginTop: 20 }}>
              <label className="mf-label" htmlFor="paste-funds">Or paste fund names (one per line, comma or semicolon separated)</label>
              <textarea id="paste-funds" className="mf-textarea" value={pasteList} onChange={(e) => setPasteList(e.target.value)} placeholder={"Parag Parikh Flexi Cap Fund - Direct Plan - Growth\nHDFC Flexi Cap Fund - Direct Plan - Growth"} />
              <div className="mf-row" style={{ justifyContent: "flex-end", marginTop: 9 }}>
                <button className="mf-button" onClick={addPastedFunds}>Add pasted funds</button>
              </div>
            </div>
            <div style={{ marginTop: 18 }}>
              <div className="mf-row" style={{ justifyContent: "space-between" }}>
                <strong>Selected funds ({selected.length}/10)</strong>
                <button className="mf-button" onClick={() => { setSelected([]); setReport(null); }}>Clear all</button>
              </div>
              <div style={{ marginTop: 8, minHeight: 42 }}>
                {selected.length ? selected.map((name) => (
                  <span className="mf-chip" key={name}>{name}<button aria-label={`Remove ${name}`} onClick={() => setSelected((items) => items.filter((item) => item !== name))}>×</button></span>
                )) : <span style={{ color: "#8b949e" }}>No funds selected yet.</span>}
              </div>
            </div>
            <div style={{ marginTop: 18 }}>
              <span className="mf-label">Analysis period</span>
              <div className="mf-period">
                {PERIODS.map((value) => <button key={value} className={period === value ? "active" : ""} onClick={() => setPeriod(value)}>{value}Y</button>)}
              </div>
            </div>
            {error && <div className="mf-error">{error}</div>}
            <button className="mf-button primary" disabled={loading || selected.length < 2 || selected.length > 10} onClick={generateReport}>
              {loading ? "Fetching NAV histories and preparing report…" : `Generate ranked report for ${selected.length} funds`}
            </button>
          </section>

          {report && (
            <section className="mf-panel">
              <div className="mf-row" style={{ justifyContent: "space-between" }}>
                <div><h2 style={{ margin: 0 }}>Your report is ready</h2><p style={{ color: "#8b949e", marginBottom: 0 }}>All selected schemes returned validated NAV histories.</p></div>
                <button className="mf-button primary" onClick={downloadPDF}>Download PDF</button>
              </div>
              <article id="comparison-report" className="mf-report">
                <header style={{ borderBottom: "3px solid #1f6feb", paddingBottom: 16 }}>
                  <div className="muted">MUTUAL FUND RESEARCH REPORT · INDIA</div>
                  <h1 style={{ fontSize: 28, margin: "8px 0" }}>Multi-Fund Performance & Risk Comparison</h1>
                  <div className="muted">{period}-year analysis · {report.fund_count} schemes · Generated {generatedDate} (local time)</div>
                </header>

                <section className="section">
                  <h2>Executive summary</h2>
                  <p>{report.executive_summary}</p>
                </section>

                <section className="section">
                  <h2>AI-assisted ranking</h2>
                  <p className="muted">Ranking is calculated from verified NAV metrics using the disclosed composite score; AI writes the evidence-based explanations.</p>
                  {report.ranked_funds.map((fund) => (
                    <div className="rank-card" key={fund.scheme_code}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                        <strong>#{fund.rank} · {fund.scheme_name}</strong>
                        <strong>{fund.comparison_score}/100</strong>
                      </div>
                      <p>{fund.ranking_reason}</p>
                      <div className="muted">CAGR {money(fund.cagr_pct)}% · Volatility {money(fund.annualized_volatility_pct)}% · Max drawdown {money(fund.max_drawdown_pct)}%</div>
                    </div>
                  ))}
                </section>

                <section className="section">
                  <h2>Side-by-side comparison</h2>
                  <table>
                    <thead><tr><th>Rank / Fund</th><th>Total return</th><th>CAGR</th><th>Volatility</th><th>Max drawdown</th><th>Score</th></tr></thead>
                    <tbody>{report.ranked_funds.map((fund) => (
                      <tr key={fund.scheme_code}><td>#{fund.rank} {fund.scheme_name}</td><td>{money(fund.total_return_pct)}%</td><td>{money(fund.cagr_pct)}%</td><td>{money(fund.annualized_volatility_pct)}%</td><td>{money(fund.max_drawdown_pct)}%</td><td>{fund.comparison_score}</td></tr>
                    ))}</tbody>
                  </table>
                </section>

                <section className="section">
                  <h2>Individual fund details</h2>
                  {report.ranked_funds.map((fund) => (
                    <div key={fund.scheme_code} className="rank-card">
                      <h3>#{fund.rank} · {fund.scheme_name}</h3>
                      <p className="muted">Scheme code: {fund.scheme_code} · ISIN: {fund.isin || "Not supplied"} · {fund.plan || "Plan not specified"} {fund.option || ""}</p>
                      <table><tbody>
                        <tr><th>Period / NAV dates</th><td>{fund.start_date} to {fund.end_date}</td></tr>
                        <tr><th>Start / end NAV</th><td>{money(fund.start_nav)} / {money(fund.latest_nav)}</td></tr>
                        <tr><th>Total return / CAGR</th><td>{money(fund.total_return_pct)}% / {money(fund.cagr_pct)}%</td></tr>
                        <tr><th>Annualized volatility</th><td>{money(fund.annualized_volatility_pct)}%</td></tr>
                        <tr><th>Maximum drawdown</th><td>{money(fund.max_drawdown_pct)}%</td></tr>
                        <tr><th>NAV observations / return intervals</th><td>{fund.observations} / {fund.periodic_returns}</td></tr>
                        <tr><th>Data source</th><td>{fund.data_source}</td></tr>
                        <tr><th>Latest NAV reconciled with AMFI scheme feed</th><td>{fund.history_latest_matches_scheme_feed ? "Yes" : "No — review freshness"}</td></tr>
                        <tr><th>Invalid rows / duplicates removed</th><td>{fund.data_quality.invalid_rows_discarded} / {fund.data_quality.duplicate_observations_removed}</td></tr>
                        <tr><th>Largest calendar gap</th><td>{fund.data_quality.largest_calendar_gap_days} days</td></tr>
                      </tbody></table>
                    </div>
                  ))}
                </section>

                <section className="section">
                  <h2>Ranking methodology & limitations</h2>
                  <p>{report.ranking_method.description}</p>
                  <ul>
                    <li>CAGR: 40% weight; higher is better.</li>
                    <li>Annualized volatility: 30% weight; lower is better.</li>
                    <li>Maximum drawdown: 30% weight; a shallower decline is better.</li>
                  </ul>
                  <p>{report.limitations}</p>
                  <p>{report.data_source_note}</p>
                  <p className="muted">Volatility is the sample standard deviation of consecutive NAV returns annualized by √252. Maximum drawdown is the largest peak-to-subsequent-trough decline in the observed NAV series. Calendar gaps are reported as quality signals and are not automatically treated as missing trading days.</p>
                </section>
                <footer style={{ borderTop: "1px solid #dce3ec", marginTop: 30, paddingTop: 14, fontSize: 11, color: "#586579" }}>
                  Disclaimer: Past performance is not indicative of future returns. This report is for informational research only and is not personalized investment advice. Mutual fund investments are subject to market risks. Read all scheme-related documents carefully.
                </footer>
              </article>
            </section>
          )}
        </>
      ) : (
        <section className="mf-panel">
          <h2>Ask the Mutual Fund AI Assistant</h2>
          <p style={{ color: "#8b949e" }}>Ask a question or analyze an individual fund using the NAV analytics pipeline.</p>
          <div className="mf-period">{PERIODS.map((value) => <button key={value} className={period === value ? "active" : ""} onClick={() => setPeriod(value)}>{value}Y</button>)}</div>
          <form onSubmit={runChat}>
            <textarea className="mf-textarea" value={chatQuery} onChange={(e) => setChatQuery(e.target.value)} placeholder="Analyze Parag Parikh Flexi Cap Fund for 1 year…" />
            <button className="mf-button primary" style={{ marginTop: 12 }} disabled={chatLoading || !chatQuery.trim()}>{chatLoading ? "Analyzing…" : "Analyze"}</button>
          </form>
          {chatHTML && <div className="mf-chat-result" dangerouslySetInnerHTML={{ __html: chatHTML }} />}
        </section>
      )}
      <footer style={{ textAlign: "center", color: "#6e7681", fontSize: 12, marginTop: 38 }}>Live NAV data · AMFI primary source · MFapi.in fallback · Research, not investment advice</footer>
    </main>
  );
}
