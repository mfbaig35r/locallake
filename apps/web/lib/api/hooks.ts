import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { components } from "./types";

export type JobRun = components["schemas"]["JobRunOut"];
export type JobList = components["schemas"]["JobListOut"];
export type NotebookEntry = components["schemas"]["NotebookEntryOut"];
export type NotebookList = components["schemas"]["NotebookListOut"];
export type NotebookDetail = components["schemas"]["NotebookDetailOut"];
export type RunNotebookRequest = components["schemas"]["RunNotebookRequest"];
export type ArtifactEntry = components["schemas"]["ArtifactEntryOut"];
export type ArtifactList = components["schemas"]["ArtifactListOut"];
export type ArtifactPreview = components["schemas"]["ArtifactPreviewOut"];
export type QueryRequest = components["schemas"]["QueryRequest"];
export type QueryResult = components["schemas"]["QueryResultOut"];
export type SavedQuery = components["schemas"]["SavedQueryOut"];
export type SavedQueryIn = components["schemas"]["SavedQueryIn"];
export type QueryHistoryEntry = components["schemas"]["QueryHistoryOut"];
export type TableEntry = components["schemas"]["TableEntryOut"];
export type TableDetail = components["schemas"]["TableDetailOut"];
export type TemplateEntry = components["schemas"]["TemplateEntryOut"];
export type CreateNotebookRequest = components["schemas"]["CreateNotebookRequest"];
export type GitStatus = components["schemas"]["GitStatusOut"];
export type GitCommit = components["schemas"]["GitCommitOut"];
export type Schedule = components["schemas"]["ScheduleOut"];
export type ScheduleIn = components["schemas"]["ScheduleIn"];
export type ScheduleUpdate = components["schemas"]["ScheduleUpdate"];

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

export function useRunQuery() {
  return useMutation({
    mutationFn: async (body: QueryRequest) => {
      const { data, error } = await api.POST("/sql/query", { body });
      if (error) throw error;
      return data!;
    },
  });
}

export function useSavedQueries() {
  return useQuery({
    queryKey: ["sql", "saved"],
    queryFn: async () => {
      const { data, error } = await api.GET("/sql/saved");
      if (error) throw error;
      return data!;
    },
  });
}

export function useCreateSavedQuery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: SavedQueryIn) => {
      const { data, error } = await api.POST("/sql/saved", { body });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sql", "saved"] }),
  });
}

export function useDeleteSavedQuery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.DELETE("/sql/saved/{saved_id}", {
        params: { path: { saved_id: id } },
      });
      if (error) throw error;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sql", "saved"] }),
  });
}

export function useQueryHistory(limit = 50) {
  return useQuery({
    queryKey: ["sql", "history", limit],
    queryFn: async () => {
      const { data, error } = await api.GET("/sql/history", {
        params: { query: { limit } },
      });
      if (error) throw error;
      return data!;
    },
  });
}

export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: async () => {
      const { data, error } = await api.GET("/templates");
      if (error) throw error;
      return data!;
    },
  });
}

export function useCreateNotebook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CreateNotebookRequest) => {
      const { data, error } = await api.POST("/notebooks", { body });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebooks"] }),
  });
}

export function useSchedules() {
  return useQuery({
    queryKey: ["schedules"],
    queryFn: async () => {
      const { data, error } = await api.GET("/schedules");
      if (error) throw error;
      return data!;
    },
    refetchInterval: 30_000,
  });
}

export function useCreateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ScheduleIn) => {
      const { data, error } = await api.POST("/schedules", { body });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useUpdateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (args: { id: string; body: ScheduleUpdate }) => {
      const { data, error } = await api.PATCH("/schedules/{schedule_id}", {
        params: { path: { schedule_id: args.id } },
        body: args.body,
      });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useDeleteSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.DELETE("/schedules/{schedule_id}", {
        params: { path: { schedule_id: id } },
      });
      if (error) throw error;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useGitStatus() {
  return useQuery({
    queryKey: ["git", "status"],
    queryFn: async () => {
      const { data, error } = await api.GET("/git/status");
      if (error) throw error;
      return data!;
    },
    refetchInterval: 30_000,
  });
}

export function useCatalogTables() {
  return useQuery({
    queryKey: ["catalog", "tables"],
    queryFn: async () => {
      const { data, error } = await api.GET("/catalog/tables");
      if (error) throw error;
      return data!;
    },
  });
}

export function useTableDetail(schema: string | null, name: string | null) {
  return useQuery({
    queryKey: ["catalog", "tables", schema, name],
    enabled: !!schema && !!name,
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/catalog/tables/{schema_name}/{name}",
        { params: { path: { schema_name: schema!, name: name! } } }
      );
      if (error) throw error;
      return data!;
    },
  });
}

export function useArtifacts(jobId: string | null) {
  return useQuery({
    queryKey: ["artifacts", jobId],
    enabled: !!jobId,
    queryFn: async () => {
      const { data, error } = await api.GET("/jobs/{job_id}/artifacts", {
        params: { path: { job_id: jobId! } },
      });
      if (error) throw error;
      return data!;
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
