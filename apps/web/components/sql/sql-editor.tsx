"use client";

import Editor, { type OnMount } from "@monaco-editor/react";
import { useCallback, useRef } from "react";

export type SqlEditorHandle = {
  getValue: () => string;
};

export function SqlEditor({
  value,
  onChange,
  onSubmit,
}: {
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
}) {
  const onSubmitRef = useRef(onSubmit);
  onSubmitRef.current = onSubmit;

  const handleMount: OnMount = useCallback((editor, monaco) => {
    editor.addCommand(
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
      () => onSubmitRef.current()
    );
  }, []);

  return (
    <div className="overflow-hidden rounded-lg border">
      <Editor
        height="280px"
        language="sql"
        value={value}
        onChange={(v: string | undefined) => onChange(v ?? "")}
        onMount={handleMount}
        theme="vs"
        options={{
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          fontFamily:
            "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
          tabSize: 2,
          padding: { top: 12, bottom: 12 },
          renderLineHighlight: "line",
          lineNumbers: "on",
          wordWrap: "on",
        }}
      />
    </div>
  );
}
