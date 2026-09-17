import { useEffect, useState } from "react";
import { marked } from "marked";
import { useRun } from "../context/RunContext";
import { reportsApi } from "../api/reports";
import { EmptyState, Loader, ErrorState } from "../components/common/Primitives";
import { IconDownload } from "../components/common/Icons";

export default function Reports() {
  const { runId } = useRun();
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function load() {
    if (!runId) return;
    setLoading(true);
    setError(null);
    reportsApi
      .getMarkdown(runId)
      .then(setMarkdown)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load report."))
      .finally(() => setLoading(false));
  }

  useEffect(load, [runId]);

  function download() {
    if (!markdown || !runId) return;
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `invincibles-report-${runId}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  if (!runId) {
    return (
      <div className="page">
        <Header />
        <EmptyState title="No report available" desc="Run a full analysis to generate a scientific report from real registration results." />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <span className="page-eyebrow">Reports</span>
          <h1 className="page-title">Scientific Report</h1>
          <p className="page-subtitle">Generated directly from this run's computed metrics — nothing here is templated with placeholder numbers.</p>
        </div>
        <button className="btn btn-secondary" onClick={download} disabled={!markdown}>
          <IconDownload style={{ width: 14, height: 14 }} />
          DOWNLOAD .MD
        </button>
      </div>

      {loading && <Loader label="Generating report from backend metrics…" />}
      {error && <ErrorState title="Could not generate report" message={error} onRetry={load} />}

      {markdown && (
        <div className="panel panel-padded">
          <div
            className="report-markdown"
            dangerouslySetInnerHTML={{ __html: marked.parse(markdown, { async: false }) as string }}
          />
        </div>
      )}
    </div>
  );
}

function Header() {
  return (
    <div className="page-header">
      <div>
        <span className="page-eyebrow">Reports</span>
        <h1 className="page-title">Scientific Report</h1>
      </div>
    </div>
  );
}
