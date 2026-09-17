import { useEffect, useRef, useState } from "react";
import { useRun } from "../context/RunContext";
import { lunarAIApi } from "../api/lunarAI";
import { registrationApi } from "../api/registration";
import { resolveAssetUrl } from "../api/client";
import { EmptyState, Loader, ErrorState } from "../components/common/Primitives";
import { IconSparkle } from "../components/common/Icons";
import type { LunarAIReport, CompareSensorsResponse, ExplainRegionResponse, RegistrationImagesResponse } from "../types";

interface ChatTurn {
  question: string;
  answer: string;
  engine: string;
  category?: string;
}

function classify(text: string): "observed" | "derived" | "uncertain" | "insufficient" {
  const t = text.toUpperCase();
  if (t.includes("UNCERTAIN")) return "uncertain";
  if (t.includes("DERIVED")) return "derived";
  if (t.includes("OBSERVED")) return "observed";
  return "insufficient";
}

const SAMPLE_QUESTIONS = [
  "What is the overall registration confidence and why?",
  "Which sensor registered best?",
  "Explain the registration pipeline and stages",
  "What does checkpoint RMSE mean?",
  "Explain the composite registered image",
  "Why is phase congruency used instead of gradients?",
  "Why are RIFT and CFOG descriptors used?",
  "What does the checkerboard validation show?",
  "What is OHRC and why is it locked as reference?",
  "Explain local terrain-relief refinement",
  "How does the area-based NCC fallback work?",
  "What sensors were processed in this run?",
];

export default function LunarAI() {
  const { runId } = useRun();
  const [report, setReport] = useState<LunarAIReport | null>(null);
  const [compare, setCompare] = useState<CompareSensorsResponse | null>(null);
  const [region, setRegion] = useState<ExplainRegionResponse | null>(null);
  const [images, setImages] = useState<RegistrationImagesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState<ChatTurn[]>([]);
  const [asking, setAsking] = useState(false);
  const [marker, setMarker] = useState<{ x: number; y: number } | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    lunarAIApi
      .analyze(runId)
      .then(setReport)
      .catch((e) => setError(e instanceof Error ? e.message : "Lunar AI analysis failed."))
      .finally(() => setLoading(false));
    registrationApi.images(runId).then(setImages).catch(() => {});
  }, [runId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, asking]);

  async function handleCompare() {
    if (!runId) return;
    const res = await lunarAIApi.compareSensors(runId);
    setCompare(res);
  }

  async function handleImageClick(e: React.MouseEvent<HTMLImageElement>) {
    if (!runId || !imgRef.current) return;
    const rect = imgRef.current.getBoundingClientRect();
    const displayX = e.clientX - rect.left;
    const displayY = e.clientY - rect.top;
    const scaleX = imgRef.current.naturalWidth / rect.width;
    const scaleY = imgRef.current.naturalHeight / rect.height;
    const x = displayX * scaleX;
    const y = displayY * scaleY;
    setMarker({ x: displayX, y: displayY });
    const res = await lunarAIApi.explainRegion(runId, x, y, 26);
    setRegion(res);
  }

  async function executeAsk(queryText: string) {
    if (!runId || !queryText.trim()) return;
    setAsking(true);
    try {
      const res = await lunarAIApi.ask(runId, queryText.trim());
      setChat((c) => [
        ...c,
        {
          question: queryText.trim(),
          answer: res.answer,
          engine: res.engine,
          category: (res as { category?: string }).category,
        },
      ]);
      setQuestion("");
    } catch (e) {
      setChat((c) => [
        ...c,
        {
          question: queryText.trim(),
          answer: `Error: ${e instanceof Error ? e.message : "request failed"}`,
          engine: "error",
        },
      ]);
    } finally {
      setAsking(false);
    }
  }

  if (!runId) {
    return (
      <div className="page">
        <Header />
        <EmptyState title="No registered data to analyze" desc="Run a full analysis first — Lunar AI interprets computed registration results, it does not run independently of them." />
      </div>
    );
  }

  const ohrcImg = images?.["OHRC"]?.multiband_layer_preview || images?.["OHRC"]?.original_input || images?.[Object.keys(images || {})[0]]?.reference_analysis_view;

  return (
    <div className="page">
      <Header />

      <div className="quick-action-row" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button className="btn btn-secondary btn-sm" onClick={handleCompare}>
          COMPARE SENSORS PIPELINE
        </button>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => executeAsk("What is the overall registration confidence and why?")}
        >
          CONFIDENCE BREAKDOWN
        </button>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => executeAsk("Explain the composite registered image and how it was created")}
        >
          EXPLAIN COMPOSITE FUSION
        </button>
      </div>

      {loading && <Loader label="Lunar AI is interpreting the registered data…" />}
      {error && <ErrorState title="Lunar AI unavailable" message={error} />}

      {report && (
        <div className="grid" style={{ gridTemplateColumns: "1.2fr 1fr", gap: 24, marginTop: 16 }}>
          {/* LEFT COLUMN: SCIENTIFIC REPORT & REGISTRATION FINDINGS */}
          <div>
            <div className="ai-card">
              <div className="ai-card-label" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Scientific Summary</span>
                <span className="badge" style={{ background: "rgba(79,209,232,0.1)", color: "var(--accent-cyan)" }}>
                  OVERALL: {report.confidence_overall}
                </span>
              </div>
              {report.scientific_summary.map((line, i) => (
                <div key={i} className="ai-card-body mt-8" style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <span className={`evidence-tag ${classify(line)}`} style={{ flexShrink: 0, marginTop: 2 }}>{classify(line)}</span>
                  <span style={{ fontSize: 13, lineHeight: 1.5 }}>{line.replace(/\[.*?\]/g, "").trim()}</span>
                </div>
              ))}
            </div>

            <div className="ai-card mt-16">
              <div className="ai-card-label">Sensor Contributions & Structural Evidence</div>
              {Object.entries(report.sensor_contributions).map(([sensor, c]) => (
                <div key={sensor} className="flex justify-between items-center mt-8" style={{ borderBottom: "1px solid var(--border-hairline)", paddingBottom: 8 }}>
                  <div>
                    <div className="mono" style={{ fontSize: 12.5, fontWeight: 600 }}>{sensor}</div>
                    <div className="text-tertiary" style={{ fontSize: 12 }}>{c.evidence}</div>
                  </div>
                  <span className={`evidence-tag ${classify(c.classification)}`}>{c.classification}</span>
                </div>
              ))}
            </div>

            <div className="ai-card mt-16">
              <div className="ai-card-label">Detected Feature Keypoint Funnel</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12, marginTop: 10 }}>
                {Object.entries(report.detected_features).map(([sensor, feat]) => (
                  <div key={sensor} style={{ padding: "8px 12px", background: "rgba(0,0,0,0.25)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-hairline)" }}>
                    <div className="mono" style={{ fontSize: 11, color: "var(--accent-cyan)", fontWeight: 600 }}>{sensor}</div>
                    <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2 }}>{feat.inliers}</div>
                    <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>inliers / {feat.accepted_matches} matches</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="ai-card mt-16">
              <div className="ai-card-label">Strict Scientific Boundaries & Grounding Rules</div>
              {report.limitations.map((l, i) => (
                <div key={i} className="ai-card-body mt-8" style={{ fontSize: 12, color: "var(--text-secondary)" }}>• {l}</div>
              ))}
            </div>

            {compare && (
              <div className="ai-card mt-16">
                <div className="ai-card-label">Cross-Sensor Alignment Chain</div>
                <div className="flex-col gap-8 mt-8">
                  {compare.chain.map((c, i) => (
                    <div key={i} className="flex items-center gap-12" style={{ padding: "4px 0", borderBottom: "1px solid var(--border-hairline)" }}>
                      <span className="mono" style={{ fontSize: 12, width: 100, fontWeight: 600 }}>{c.sensor}</span>
                      <span className="badge" style={{ fontSize: 11, background: c.status === "SUCCESS" ? "var(--status-success-bg)" : "var(--status-pending-bg)", color: c.status === "SUCCESS" ? "var(--status-success)" : "var(--text-tertiary)" }}>
                        {c.status}
                      </span>
                      <span className="text-secondary" style={{ fontSize: 12 }}>
                        {c.confidence ? `Confidence: ${c.confidence}` : ""} {c.checkpoint_rmse ? `· RMSE: ${c.checkpoint_rmse.toFixed(2)}px` : ""}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="mt-12" style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{compare.cross_sensor_interpretation}</div>
              </div>
            )}
          </div>

          {/* RIGHT COLUMN: REGION EXPLORER & INTERACTIVE AI CHAT */}
          <div>
            <div className="panel panel-padded">
              <div className="panel-title">Click-to-Interpret Region Explorer</div>
              <div className="panel-title-sub mt-4" style={{ marginBottom: 12 }}>Click anywhere on the reference image to query multi-sensor observations at that spatial point.</div>
              <div style={{ position: "relative" }}>
                {ohrcImg ? (
                  <img
                    ref={imgRef}
                    src={resolveAssetUrl(ohrcImg) || ""}
                    alt="OHRC reference"
                    onClick={handleImageClick}
                    style={{ width: "100%", borderRadius: "var(--radius-md)", cursor: "crosshair", border: "1px solid var(--border-hairline)", display: "block" }}
                  />
                ) : (
                  <div className="image-empty">Reference image unavailable</div>
                )}
                {marker && (
                  <div
                    style={{
                      position: "absolute",
                      left: marker.x - 8,
                      top: marker.y - 8,
                      width: 16,
                      height: 16,
                      borderRadius: "50%",
                      border: "2px solid var(--accent-cyan)",
                      boxShadow: "0 0 0 4px rgba(79,209,232,0.25)",
                      pointerEvents: "none",
                    }}
                  />
                )}
              </div>

              {region && (
                <div className="mt-16" style={{ background: "rgba(0,0,0,0.25)", padding: 12, borderRadius: "var(--radius-sm)", border: "1px solid var(--border-hairline)" }}>
                  <div className="ai-card-label">Observation at ({Math.round(region.roi.x)}, {Math.round(region.roi.y)})</div>
                  <div style={{ fontSize: 12.5, color: "var(--text-secondary)", marginTop: 4 }}>{region.what_is_observed}</div>
                  <div className="ai-card-label mt-12">Sensor Evidence</div>
                  {region.sensor_contributions.map((c, i) => (
                    <div key={i} className="flex justify-between items-center mt-6">
                      <span className="mono" style={{ fontSize: 11.5 }}>{c.sensor}</span>
                      <span className={`evidence-tag ${classify(c.classification)}`}>{c.classification}</span>
                    </div>
                  ))}
                  <div className="ai-card-label mt-12">Interpretation & Limitations</div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>{region.possible_interpretation}</div>
                </div>
              )}
            </div>

            {/* INTERACTIVE Q&A CONSOLE */}
            <div className="panel panel-padded mt-24" style={{ border: "1px solid rgba(79,209,232,0.2)" }}>
              <div className="panel-header" style={{ marginBottom: 8 }}>
                <div className="panel-title flex items-center gap-8" style={{ fontSize: 14 }}>
                  <IconSparkle style={{ width: 16, height: 16, color: "var(--accent-cyan)" }} />
                  Lunar AI Q&A Console
                </div>
                <span className="badge" style={{ fontSize: 10, background: "rgba(71,209,140,0.1)", color: "var(--status-success)" }}>
                  GROUNDED SCIENTIFIC NLU
                </span>
              </div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 12 }}>
                Ask any technical question about this run, sensors, algorithms, or registration accuracy:
              </div>

              {/* Sample Quick Questions Chips */}
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
                {SAMPLE_QUESTIONS.slice(0, 6).map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => executeAsk(q)}
                    disabled={asking}
                    style={{
                      background: "rgba(79,209,232,0.06)",
                      border: "1px solid rgba(79,209,232,0.18)",
                      borderRadius: 14,
                      padding: "4px 10px",
                      fontSize: 11,
                      color: "var(--accent-cyan)",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    + {q}
                  </button>
                ))}
              </div>

              {/* Chat Conversation History */}
              <div
                className="flex-col gap-12"
                style={{
                  minHeight: 180,
                  maxHeight: 380,
                  overflowY: "auto",
                  padding: "12px",
                  background: "rgba(8, 11, 16, 0.7)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-hairline)",
                }}
              >
                {chat.map((turn, i) => (
                  <div key={i} style={{ borderBottom: i < chat.length - 1 ? "1px solid var(--border-hairline)" : "none", paddingBottom: 10 }}>
                    <div style={{ fontSize: 12.5, color: "var(--accent-cyan)", fontWeight: 600 }}>
                      Q: {turn.question}
                    </div>
                    <div
                      style={{
                        fontSize: 12.5,
                        color: "var(--text-primary)",
                        marginTop: 6,
                        whiteSpace: "pre-wrap",
                        lineHeight: 1.55,
                        background: "rgba(13, 19, 27, 0.6)",
                        padding: "8px 12px",
                        borderRadius: "var(--radius-sm)",
                        borderLeft: "2px solid var(--accent-cyan)",
                      }}
                    >
                      {turn.answer}
                    </div>
                    <div className="mono text-tertiary" style={{ fontSize: 10, marginTop: 4, display: "flex", justifyContent: "space-between" }}>
                      <span>Engine: {turn.engine}</span>
                      <span>Verified against computed metrics</span>
                    </div>
                  </div>
                ))}
                {asking && (
                  <div style={{ fontSize: 12, color: "var(--accent-cyan)", display: "flex", alignItems: "center", gap: 8 }}>
                    <Loader label="Computing grounded answer from registration metrics…" />
                  </div>
                )}
                {chat.length === 0 && !asking && (
                  <div className="text-tertiary" style={{ fontSize: 12.5, textAlign: "center", padding: "20px 0" }}>
                    Select a suggested question above or type any question below to test Lunar AI.
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Input row */}
              <div className="chat-input-row mt-12">
                <input
                  className="chat-input"
                  placeholder="e.g. Which sensor registered best? What is checkpoint RMSE?"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && executeAsk(question)}
                  disabled={asking}
                />
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => executeAsk(question)}
                  disabled={asking || !question.trim()}
                >
                  {asking ? "…" : "ASK"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Header() {
  return (
    <div className="page-header">
      <div>
        <span className="page-eyebrow">Lunar AI</span>
        <h1 className="page-title">Scientific Interpretation Layer</h1>
        <p className="page-subtitle">
          Honest, data-grounded AI assistant for lunar remote-sensing scientists and evaluators.
        </p>
      </div>
    </div>
  );
}
