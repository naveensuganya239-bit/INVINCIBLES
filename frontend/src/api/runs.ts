import { api } from "./client";
import type { RunHistoryResponse } from "../types";

export const runsApi = {
  list: () => api.get<RunHistoryResponse>("/api/runs"),
};
