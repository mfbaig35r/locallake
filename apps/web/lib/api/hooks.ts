import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { components } from "./types";

export type JobRun = components["schemas"]["JobRunOut"];
export type JobList = components["schemas"]["JobListOut"];
export type NotebookEntry = components["schemas"]["NotebookEntryOut"];
export type NotebookList = components["schemas"]["NotebookListOut"];
export type NotebookDetail = components["schemas"]["NotebookDetailOut"];
export type RunNotebookRequest = components["schemas"]["RunNotebookRequest"];

const JOBS_POLL_MS = 3000;

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error } = await api.GET("/health");
      if (error) throw error;
      return data;
    },
    refetchInterval: 10_000,
  });
}

export function useNotebooks() {
  return useQuery({
    queryKey: ["notebooks"],
    queryFn: async () => {
      const { data, error } = await api.GET("/notebooks");
      if (error) throw error;
      return data!;
    },
  });
}

export function useNotebook(path: string | null) {
  return useQuery({
    queryKey: ["notebooks", path],
    enabled: !!path,
    queryFn: async () => {
      const { data, error } = await api.GET("/notebooks/{notebook_path}", {
        params: { path: { notebook_path: path! } },
      });
      if (error) throw error;
      return data!;
    },
  });
}

export function useJobs(opts: {
  status?: string;
  notebookPath?: string;
  limit?: number;
  offset?: number;
} = {}) {
  return useQuery({
    queryKey: ["jobs", opts],
    queryFn: async () => {
      const { data, error } = await api.GET("/jobs", {
        params: {
          query: {
            status: opts.status,
            notebook_path: opts.notebookPath,
            limit: opts.limit ?? 50,
            offset: opts.offset ?? 0,
          },
        },
      });
      if (error) throw error;
      return data!;
    },
    refetchInterval: (q) => {
      const items = (q.state.data as JobList | undefined)?.items ?? [];
      const hasActive = items.some(
        (j) => j.status === "queued" || j.status === "running"
      );
      return hasActive ? JOBS_POLL_MS : 15_000;
    },
  });
}

export function useJob(id: string | null) {
  return useQuery({
    queryKey: ["jobs", id],
    enabled: !!id,
    queryFn: async () => {
      const { data, error } = await api.GET("/jobs/{job_id}", {
        params: { path: { job_id: id! } },
      });
      if (error) throw error;
      return data!;
    },
    refetchInterval: (q) => {
      const job = q.state.data as JobRun | undefined;
      if (!job) return false;
      return job.status === "queued" || job.status === "running"
        ? JOBS_POLL_MS
        : false;
    },
  });
}

export function useRunNotebook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { path: string; body?: RunNotebookRequest }) => {
      const { data, error } = await api.POST(
        "/notebooks/{notebook_path}/run",
        {
          params: { path: { notebook_path: args.path } },
          body: args.body ?? {
            parameters: {},
            timeout_seconds: 300,
            triggered_by: "ui",
          },
        }
      );
      if (error) throw error;
      return data!;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useCancelJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (jobId: string) => {
      const { data, error } = await api.POST("/jobs/{job_id}/cancel", {
        params: { path: { job_id: jobId } },
      });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
