"use client";

import { Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateNotebook, useTemplates } from "@/lib/api/hooks";

export function NewNotebookModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (notebookPath: string) => void;
}) {
  const templates = useTemplates();
  const create = useCreateNotebook();
  const [template, setTemplate] = useState<string>("");
  const [name, setName] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setName("");
    const first = templates.data?.items?.[0]?.name;
    if (first) setTemplate(first);
  }, [open, templates.data]);

  if (!open) return null;

  const trimmedName = name.trim();
  const sanitizedName =
    trimmedName.endsWith(".py") || trimmedName === ""
      ? trimmedName
      : `${trimmedName}.py`;
  const canSubmit = !!template && !!sanitizedName && !create.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const result = await create.mutateAsync({
        template,
        name: sanitizedName,
      });
      onCreated(result.path);
      onClose();
    } catch (err: unknown) {
      if (err && typeof err === "object" && "detail" in err) {
        setError(String((err as { detail: unknown }).detail));
      } else {
        setError(err instanceof Error ? err.message : "create failed");
      }
    }
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-background/60 backdrop-blur-sm"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
      role="dialog"
      aria-modal="true"
      tabIndex={-1}
    >
      <div
        className="w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="document"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight">New notebook</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block space-y-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Template
            </span>
            {templates.isLoading ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading templates…
              </div>
            ) : templates.data?.items?.length ? (
              <select
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-mono"
              >
                {templates.data.items.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.name}
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-xs text-muted-foreground">
                No templates in <code>workspace/templates</code>.
              </p>
            )}
          </label>

          <label className="block space-y-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Name
            </span>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my_notebook"
              className="font-mono text-sm"
              autoFocus
            />
            {sanitizedName && sanitizedName !== name ? (
              <p className="font-mono text-[11px] text-muted-foreground">
                → {sanitizedName}
              </p>
            ) : null}
          </label>

          {error ? (
            <p className="rounded-md bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
              {error}
            </p>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onClose}
              disabled={create.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={!canSubmit}>
              {create.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : null}
              Create
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
