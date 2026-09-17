import { API_BASE_URL } from "./client";

export const reportsApi = {
  /** The backend returns raw Markdown text (PlainTextResponse). */
  getMarkdown: async (runId: string): Promise<string> => {
    const res = await fetch(`${API_BASE_URL}/api/report?run_id=${encodeURIComponent(runId)}`);
    if (!res.ok) throw new Error(`Failed to fetch report (status ${res.status})`);
    return res.text();
  },
  downloadUrl: (runId: string) => `${API_BASE_URL}/api/report?run_id=${encodeURIComponent(runId)}`,
};
