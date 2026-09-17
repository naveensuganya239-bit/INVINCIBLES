import { api } from "./client";
import type { LunarAIReport, ExplainRegionResponse, CompareSensorsResponse, AskLunarAIResponse } from "../types";

export const lunarAIApi = {
  analyze: (runId: string) => api.post<LunarAIReport>("/api/lunar-ai/analyze", { run_id: runId }),
  explainRegion: (runId: string, x: number, y: number, radius = 24) =>
    api.post<ExplainRegionResponse>("/api/lunar-ai/explain-region", { run_id: runId, x, y, radius }),
  compareSensors: (runId: string) =>
    api.post<CompareSensorsResponse>("/api/lunar-ai/compare-sensors", { run_id: runId }),
  ask: (runId: string, question: string) =>
    api.post<AskLunarAIResponse>("/api/lunar-ai/ask", { run_id: runId, question }),
};
