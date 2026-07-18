import { useEffect, useState } from "react";
import { auditApi } from "../services/api";

interface AuditEvent {
  id: string;
  timestamp: string;
  agent_name: string;
  action_type: string;
  verdict: "safe" | "flagged" | "blocked";
  threat_category: string;
  threat_score: number;
  llm_reasoning?: string;
  action_details?: any;
}

interface AuditSummary {
  total_events: number;
  blocked_events: number;
  flagged_events: number;
  average_threat_score: number;
  manipulation_types: Record<string, number>;
}

export default function AuditDashboard() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [eventsRes, summaryRes] = await Promise.all([
          auditApi.getEvents(),
          auditApi.getSummary(),
        ]);
        setEvents(eventsRes.data);
        setSummary(summaryRes.data);
      } catch (error) {
        console.error("Failed to fetch audit data", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !events.length) return <div style={{ padding: 20 }}>Loading audit data...</div>;

  return (
    <div style={{ padding: 20, fontFamily: "sans-serif" }}>
      <h2>Agent Auditor Dashboard</h2>
      
      {summary && (
        <div style={{ 
          display: "flex", 
          gap: 20, 
          marginBottom: 30,
          background: "#f8f9fa",
          padding: 20,
          borderRadius: 8,
          border: "1px solid #e9ecef"
        }}>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: "0 0 10px 0" }}>Overview</h3>
            <p style={{ margin: 5 }}><strong>Total Events:</strong> {summary.total_events}</p>
            <p style={{ margin: 5 }}><strong>Blocked:</strong> <span style={{ color: "#dc3545" }}>{summary.blocked_events}</span></p>
            <p style={{ margin: 5 }}><strong>Flagged:</strong> <span style={{ color: "#fd7e14" }}>{summary.flagged_events}</span></p>
            <p style={{ margin: 5 }}><strong>Avg Risk Score:</strong> {summary.average_threat_score.toFixed(2)}</p>
          </div>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: "0 0 10px 0" }}>Threat Types</h3>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {Object.entries(summary.manipulation_types).map(([type, count]) => (
                <li key={type}>{type}: <strong>{count}</strong></li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <h3>Recent Audit Events</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
        <thead>
          <tr style={{ background: "#f1f3f5", borderBottom: "2px solid #dee2e6" }}>
            <th style={{ padding: 10 }}>Time</th>
            <th style={{ padding: 10 }}>Agent</th>
            <th style={{ padding: 10 }}>Action</th>
            <th style={{ padding: 10 }}>Verdict</th>
            <th style={{ padding: 10 }}>Score</th>
            <th style={{ padding: 10 }}>Category</th>
            <th style={{ padding: 10 }}>Reasoning</th>
          </tr>
        </thead>
        <tbody>
          {events.map((ev) => (
            <tr key={ev.id} style={{ borderBottom: "1px solid #e9ecef" }}>
              <td style={{ padding: 10 }}>{new Date(ev.timestamp).toLocaleTimeString()}</td>
              <td style={{ padding: 10, fontWeight: "bold" }}>{ev.agent_name}</td>
              <td style={{ padding: 10 }}>
                <code>{ev.action_type}</code>
              </td>
              <td style={{ padding: 10 }}>
                <span style={{
                  padding: "4px 8px",
                  borderRadius: 4,
                  fontSize: "0.85em",
                  fontWeight: "bold",
                  background: ev.verdict === "blocked" ? "#ffe3e3" : ev.verdict === "flagged" ? "#fff3cd" : "#d3f9d8",
                  color: ev.verdict === "blocked" ? "#c92a2a" : ev.verdict === "flagged" ? "#f59f00" : "#2b8a3e"
                }}>
                  {ev.verdict.toUpperCase()}
                </span>
              </td>
              <td style={{ padding: 10 }}>
                <span style={{ color: ev.threat_score >= 80 ? "#dc3545" : ev.threat_score >= 50 ? "#fd7e14" : "inherit" }}>
                  {ev.threat_score.toFixed(1)}
                </span>
              </td>
              <td style={{ padding: 10 }}>{ev.threat_category !== "none" ? ev.threat_category : "-"}</td>
              <td style={{ padding: 10, fontSize: "0.9em", color: "#495057", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={ev.llm_reasoning}>
                {ev.llm_reasoning || "-"}
              </td>
            </tr>
          ))}
          {events.length === 0 && (
            <tr>
              <td colSpan={7} style={{ padding: 20, textAlign: "center", color: "#868e96" }}>
                No audit events recorded yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
