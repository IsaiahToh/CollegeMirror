import { useEffect, useRef, useState } from "react";
import { apiUrl } from "../lib/api";
import { saveExampleSetId } from "../lib/storage";

interface ExamplePair {
  id: number;
  idmlFile: File | null;
  wordFiles: File[];
}

interface IngestionResult {
  example_set_id: string;
  message: string;
}

type IngestionStatus = "running" | "completed" | "failed";

function useIngestionStatus(exampleSetId: string | null) {
  const [status, setStatus] = useState<IngestionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!exampleSetId) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(apiUrl(`/examples/${exampleSetId}/status`));
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) {
          setStatus(data.status);
          if (data.status === "failed") setError(data.error ?? "Ingestion failed.");
          if (data.status === "running") setTimeout(poll, 3000);
        }
      } catch {
        // network blip — retry
        if (!cancelled) setTimeout(poll, 5000);
      }
    };

    poll();
    return () => { cancelled = true; };
  }, [exampleSetId]);

  return { status, error };
}

let _nextId = 1;
const nextId = () => _nextId++;

function PairCard({
  pair,
  index,
  onUpdate,
  onRemove,
  canRemove,
}: {
  pair: ExamplePair;
  index: number;
  onUpdate: (updated: ExamplePair) => void;
  onRemove: () => void;
  canRemove: boolean;
}) {
  const idmlRef = useRef<HTMLInputElement>(null);
  const wordRef = useRef<HTMLInputElement>(null);

  const handleIdml = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    onUpdate({ ...pair, idmlFile: file });
    e.target.value = "";
  };

  const handleWords = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    onUpdate({ ...pair, wordFiles: [...pair.wordFiles, ...picked] });
    e.target.value = "";
  };

  const removeWord = (idx: number) => {
    onUpdate({ ...pair, wordFiles: pair.wordFiles.filter((_, i) => i !== idx) });
  };

  const isComplete = pair.idmlFile !== null && pair.wordFiles.length > 0;

  return (
    <div className="glass overflow-hidden transition-all duration-200 hover:border-white/20">
      {/* Card header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div
            className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold transition-colors ${
              isComplete ? "bg-accent-500 text-ink-950 shadow-glow-sm" : "bg-white/[0.07] text-slate-400"
            }`}
          >
            {isComplete ? (
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            ) : index + 1}
          </div>
          <span className="text-sm font-semibold text-slate-200">Example pair {index + 1}</span>
        </div>
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="flex cursor-pointer items-center gap-1 text-xs font-medium text-slate-500 transition-colors hover:text-rose-400"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Remove
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-5 p-5 md:grid-cols-2">
        {/* IDML slot */}
        <div>
          <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
            InDesign file (.idml)
          </p>
          {pair.idmlFile ? (
            <div className="flex items-center gap-3 rounded-xl border border-accent-400/20 bg-accent-500/[0.08] px-3 py-2.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent-500/15">
                <svg className="h-4 w-4 text-accent-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <span className="flex-1 truncate text-xs font-medium text-accent-200">{pair.idmlFile.name}</span>
              <button
                type="button"
                onClick={() => onUpdate({ ...pair, idmlFile: null })}
                aria-label="Remove IDML file"
                className="flex h-5 w-5 cursor-pointer items-center justify-center rounded text-accent-300/60 transition-colors hover:bg-rose-500/10 hover:text-rose-400"
              >
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => idmlRef.current?.click()}
              className="w-full cursor-pointer rounded-xl border-2 border-dashed border-white/15 py-5 text-sm text-slate-500 transition-all duration-200 hover:border-accent-400/50 hover:bg-accent-500/[0.05] hover:text-accent-300"
            >
              <svg className="mx-auto mb-1 h-5 w-5 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              Select .idml file
            </button>
          )}
          <input ref={idmlRef} type="file" accept=".idml" className="hidden" onChange={handleIdml} />
        </div>

        {/* Word docs slot */}
        <div>
          <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Source Word documents (.docx)
          </p>
          <div className="space-y-1.5">
            {pair.wordFiles.map((f, i) => (
              <div key={i} className="flex items-center gap-3 rounded-xl border border-emerald-400/20 bg-emerald-500/[0.08] px-3 py-2">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald-500/15">
                  <svg className="h-3.5 w-3.5 text-emerald-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <span className="flex-1 truncate text-xs font-medium text-emerald-200">{f.name}</span>
                <button
                  type="button"
                  onClick={() => removeWord(i)}
                  aria-label={`Remove ${f.name}`}
                  className="flex h-5 w-5 cursor-pointer items-center justify-center rounded text-emerald-300/60 transition-colors hover:bg-rose-500/10 hover:text-rose-400"
                >
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => wordRef.current?.click()}
              className="w-full cursor-pointer rounded-xl border-2 border-dashed border-white/15 py-4 text-sm text-slate-500 transition-all duration-200 hover:border-emerald-400/50 hover:bg-emerald-500/[0.05] hover:text-emerald-300"
            >
              {pair.wordFiles.length === 0 ? (
                <>
                  <svg className="mx-auto mb-1 h-5 w-5 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                  </svg>
                  Add .docx file(s)
                </>
              ) : (
                "+ Add another .docx"
              )}
            </button>
          </div>
          <input ref={wordRef} type="file" accept=".docx" multiple className="hidden" onChange={handleWords} />
        </div>
      </div>
    </div>
  );
}

export default function ExamplesPage() {
  const [pairs, setPairs] = useState<ExamplePair[]>([
    { id: nextId(), idmlFile: null, wordFiles: [] },
  ]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const { status: ingestionStatus, error: ingestionError } = useIngestionStatus(
    result?.example_set_id ?? null
  );

  // Persist the ID once training succeeds so the Generate page can prefill it.
  useEffect(() => {
    if (ingestionStatus === "completed" && result) {
      saveExampleSetId(result.example_set_id);
    }
  }, [ingestionStatus, result]);

  const copyId = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.example_set_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable — the ID is still selectable
    }
  };

  const updatePair = (id: number, updated: ExamplePair) =>
    setPairs((prev) => prev.map((p) => (p.id === id ? updated : p)));

  const removePair = (id: number) =>
    setPairs((prev) => prev.filter((p) => p.id !== id));

  const addPair = () =>
    setPairs((prev) => [...prev, { id: nextId(), idmlFile: null, wordFiles: [] }]);

  const completedCount = pairs.filter((p) => p.idmlFile && p.wordFiles.length > 0).length;
  const canSubmit = !loading && pairs.length > 0 && completedCount === pairs.length;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSubmitError(null);
    setResult(null);

    const form = new FormData();
    const grouping: { idml: string; words: string[] }[] = [];

    for (const pair of pairs) {
      if (!pair.idmlFile) continue;
      form.append("files", pair.idmlFile, pair.idmlFile.name);
      const wordNames: string[] = [];
      for (const wf of pair.wordFiles) {
        form.append("files", wf, wf.name);
        wordNames.push(wf.name);
      }
      grouping.push({ idml: pair.idmlFile.name, words: wordNames });
    }

    form.append("grouping", JSON.stringify(grouping));

    try {
      const res = await fetch(apiUrl("/examples"), { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      setResult(data as IngestionResult);
    } catch (err) {
      setSubmitError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-10">
      {/* Page header */}
      <div className="animate-fade-up space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-accent-300">
          Step 01 — Train
        </p>
        <h1 className="font-display text-4xl font-medium tracking-tight text-white md:text-5xl">
          Teach it your design language
        </h1>
        <p className="max-w-xl text-sm leading-relaxed text-slate-400">
          Upload InDesign (.idml) files paired with the Word documents that provided their content.
          Each IDML can reference <em>one or more</em> Word sources. CollegeMirror analyses the pairs
          to learn your design patterns.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {pairs.map((pair, i) => (
          <div key={pair.id} className="animate-fade-up" style={{ animationDelay: `${100 + i * 80}ms` }}>
            <PairCard
              pair={pair}
              index={i}
              onUpdate={(updated) => updatePair(pair.id, updated)}
              onRemove={() => removePair(pair.id)}
              canRemove={pairs.length > 1}
            />
          </div>
        ))}

        <button
          type="button"
          onClick={addPair}
          className="animate-fade-up flex w-full cursor-pointer items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-white/15 py-3.5 text-sm text-slate-500 transition-all duration-200 hover:border-accent-400/50 hover:bg-accent-500/[0.05] hover:text-accent-300"
          style={{ animationDelay: "260ms" }}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add another example pair
        </button>

        {/* Submit row */}
        <div className="animate-fade-up flex items-center justify-between pt-2" style={{ animationDelay: "340ms" }}>
          {pairs.length > 0 && (
            <p className="text-xs text-slate-500">
              {completedCount}/{pairs.length} pair{pairs.length !== 1 ? "s" : ""} ready
            </p>
          )}
          <button type="submit" disabled={!canSubmit} className="btn-primary ml-auto">
            {loading ? (
              <>
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Uploading…
              </>
            ) : (
              <>
                Analyse {pairs.length} pair{pairs.length !== 1 ? "s" : ""}
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>
      </form>

      {submitError && (
        <div className="glass flex items-start gap-3 border-rose-400/30 p-4">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-rose-300">{submitError}</p>
        </div>
      )}

      {result && (
        <div
          className={`glass space-y-4 p-5 transition-colors duration-300 ${
            ingestionStatus === "completed" ? "border-emerald-400/30" :
            ingestionStatus === "failed" ? "border-rose-400/30" :
            "border-accent-400/25"
          }`}
        >
          {/* Status header */}
          <div className="flex items-center gap-3">
            {ingestionStatus === "completed" ? (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-emerald-400/25 bg-emerald-500/15">
                <svg className="h-4 w-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
            ) : ingestionStatus === "failed" ? (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-rose-400/25 bg-rose-500/15">
                <svg className="h-4 w-4 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
            ) : (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-accent-400/25 bg-accent-500/15">
                <svg className="h-4 w-4 animate-spin text-accent-400" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            )}
            <div>
              <p className={`text-sm font-semibold ${
                ingestionStatus === "completed" ? "text-emerald-300" :
                ingestionStatus === "failed" ? "text-rose-300" :
                "text-accent-300"
              }`}>
                {ingestionStatus === "completed" ? "Training complete" :
                 ingestionStatus === "failed" ? "Training failed" :
                 "Training in progress…"}
              </p>
              <p className="mt-0.5 text-xs text-slate-400">
                {ingestionStatus === "completed"
                  ? "Claude has analysed your examples. The ID below is saved for the Generate page."
                  : ingestionStatus === "failed"
                  ? "See the error below. Check your files and try again."
                  : "Claude is analysing your example pairs — this takes 30–120 seconds."}
              </p>
            </div>
          </div>

          {/* Shimmer while running */}
          {ingestionStatus !== "completed" && ingestionStatus !== "failed" && (
            <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
              <div className="animate-shimmer h-full w-1/3 bg-gradient-to-r from-transparent via-accent-400 to-transparent" />
            </div>
          )}

          {/* Error detail */}
          {ingestionStatus === "failed" && ingestionError && (
            <div className="rounded-xl border border-rose-400/25 bg-rose-500/[0.08] px-4 py-3">
              <p className="font-mono text-xs text-rose-200/90">{ingestionError}</p>
            </div>
          )}

          {/* ID — only shown when ready */}
          {ingestionStatus === "completed" && (
            <div className="flex items-end justify-between gap-3 rounded-xl border border-emerald-400/20 bg-white/[0.03] px-4 py-3">
              <div className="min-w-0 space-y-1">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Example Set ID</p>
                <p className="select-all truncate font-mono text-sm font-semibold text-slate-100">
                  {result.example_set_id}
                </p>
              </div>
              <button
                type="button"
                onClick={copyId}
                aria-label="Copy example set ID"
                className={`flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all duration-200 ${
                  copied
                    ? "border-emerald-400/30 bg-emerald-500/15 text-emerald-300"
                    : "border-white/10 bg-white/[0.05] text-slate-300 hover:border-accent-400/30 hover:text-accent-300"
                }`}
              >
                {copied ? (
                  <>
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    Copied
                  </>
                ) : (
                  <>
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
