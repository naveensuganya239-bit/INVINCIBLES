import { api } from "./client";
import type { DatasetManifest, DatasetAnalysisResponse } from "../types";

export const datasetApi = {
  getDataset: () => api.get<DatasetManifest>("/api/dataset"),
  getAnalysis: () => api.get<DatasetAnalysisResponse>("/api/dataset/analysis"),
};
