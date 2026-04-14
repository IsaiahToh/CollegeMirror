import { useEffect, useRef, useState } from "react";

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
        const res = await fetch(`/examples/${exampleSetId}/status`);
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
    <div className={`rounded-xl border bg-white shadow-card overflow-hidden transition-all duration-150 ${isComplete ? "border-slate-200" : "border-slate-200"}`}>
      {/* Card header */}
      <div className="flex items-center justify-between px-5 py-3.5 bg-slate-50 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${isComplete ? "bg-brand-600 text-white" : "bg-slate-200 text-slate-500"}`}>
            {isComplete ? (
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            ) : index + 1}
          </div>
          <span className="text-sm font-semibold text-slate-700">Example pair {index + 1}</span>
        </div>
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="text-xs text-slate-400 hover:text-red-500 font-medium transition-colors cursor-pointer flex items-center gap-1"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Remove
          </button>
        )}
      </div>

      <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* IDML slot */}
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
            InDesign file (.idml)
          </p>
          {pair.idmlFile ? (
            <div className="flex items-center gap-3 bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-2.5">
              <div className="w-8 h-8 rounded-md bg-indigo-100 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <span className="text-xs text-indigo-800 font-medium truncate flex-1">{pair.idmlFile.name}</span>
              <button
                type="button"
                onClick={() => onUpdate({ ...pair, idmlFile: null })}
                aria-label="Remove IDML file"
                className="w-5 h-5 flex items-center justify-center rounded text-indigo-400 hover:text-red-500 hover:bg-red-50 transition-colors cursor-pointer"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => idmlRef.current?.click()}
              className="w-full rounded-lg border-2 border-dashed border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 py-5 text-sm text-slate-400 hover:text-indigo-600 transition-all duration-150 cursor-pointer"
            >
              <svg className="w-5 h-5 mx-auto mb-1 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              Select .idml file
            </button>
          )}
          <input ref={idmlRef} type="file" accept=".idml" className="hidden" onChange={handleIdml} />
        </div>

        {/* Word docs slot */}
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
            Source Word documents (.docx)
          </p>
          <div className="space-y-1.5">
            {pair.wordFiles.map((f, i) => (
              <div key={i} className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                <div className="w-7 h-7 rounded-md bg-emerald-100 flex items-center justify-center shrink-0">
                  <svg className="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <span className="text-xs text-emerald-800 font-medium truncate flex-1">{f.name}</span>
                <button
                  type="button"
                  onClick={() => removeWord(i)}
                  aria-label={`Remove ${f.name}`}
                  className="w-5 h-5 flex items-center justify-center rounded text-emerald-400 hover:text-red-500 hover:bg-red-50 transition-colors cursor-pointer"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => wordRef.current?.click()}
              className="w-full rounded-lg border-2 border-dashed border-slate-200 hover:border-emerald-300 hover:bg-emerald-50 py-4 text-sm text-slate-400 hover:text-emerald-600 transition-all duration-150 cursor-pointer"
            >
              {pair.wordFiles.length === 0 ? (
                <>
                  <svg className="w-5 h-5 mx-auto mb-1 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
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
  const { status: ingestionStatus, error: ingestionError } = useIngestionStatus(
    result?.example_set_id ?? null
  );

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
      const res = await fetch("/examples", { method: "POST", body: form });
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
    <div className="space-y-8 max-w-4xl">
      {/* Page header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-xs font-semibold text-brand-600 uppercase tracking-wider mb-2">
          <span className="w-5 h-5 rounded-full bg-brand-100 flex items-center justify-center text-[10px] font-bold text-brand-700">1</span>
          Step one
        </div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Train on example documents</h1>
        <p className="text-sm text-slate-500 max-w-xl leading-relaxed">
          Upload InDesign (.idml) files paired with the Word documents that provided their content.
          Each IDML can reference <em>one or more</em> Word sources. CollegeMirror analyses the pairs
          to learn your design patterns.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {pairs.map((pair, i) => (
          <PairCard
            key={pair.id}
            pair={pair}
            index={i}
            onUpdate={(updated) => updatePair(pair.id, updated)}
            onRemove={() => removePair(pair.id)}
            canRemove={pairs.length > 1}
          />
        ))}

        <button
          type="button"
          onClick={addPair}
          className="w-full rounded-xl border-2 border-dashed border-slate-200 hover:border-brand-300 hover:bg-brand-50 py-3.5 text-sm text-slate-400 hover:text-brand-600 transition-all duration-150 flex items-center justify-center gap-2 cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add another example pair
        </button>

        {/* Submit row */}
        <div className="flex items-center justify-between pt-2">
          {pairs.length > 0 && (
            <p className="text-xs text-slate-400">
              {completedCount}/{pairs.length} pair{pairs.length !== 1 ? "s" : ""} ready
            </p>
          )}
          <button
            type="submit"
            disabled={!canSubmit}
            className="ml-auto flex items-center gap-2 px-6 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-slate-200 disabled:text-slate-400 text-white text-sm font-semibold rounded-lg shadow-sm hover:shadow-md transition-all duration-150 cursor-pointer disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Uploading…
              </>
            ) : (
              <>
                Analyse {pairs.length} pair{pairs.length !== 1 ? "s" : ""}
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>
      </form>

      {submitError && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex items-start gap-3">
          <svg className="w-4 h-4 text-red-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-red-700">{submitError}</p>
        </div>
      )}

      {result && (
        <div className={`rounded-xl border p-5 space-y-4 transition-colors ${
          ingestionStatus === "completed" ? "border-emerald-200 bg-emerald-50" :
          ingestionStatus === "failed"    ? "border-red-200 bg-red-50" :
          "border-brand-200 bg-brand-50"
        }`}>
          {/* Status header */}
          <div className="flex items-center gap-3">
            {ingestionStatus === "completed" ? (
              <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
            ) : ingestionStatus === "failed" ? (
              <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
            ) : (
              <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-brand-600 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            )}
            <div>
              <p className={`text-sm font-semibold ${
                ingestionStatus === "completed" ? "text-emerald-800" :
                ingestionStatus === "failed"    ? "text-red-700" :
                "text-brand-800"
              }`}>
                {ingestionStatus === "completed" ? "Training complete" :
                 ingestionStatus === "failed"    ? "Training failed" :
                 "Training in progress…"}
              </p>
              <p className={`text-xs mt-0.5 ${
                ingestionStatus === "completed" ? "text-emerald-600" :
                ingestionStatus === "failed"    ? "text-red-600" :
                "text-brand-600"
              }`}>
                {ingestionStatus === "completed"
                  ? "Claude has analysed your examples. Copy the ID below to use on the Generate page."
                  : ingestionStatus === "failed"
                  ? "See the error below. Check your files and try again."
                  : "Claude is analysing your example pairs — this takes 30–120 seconds."}
              </p>
            </div>
          </div>

          {/* Error detail */}
          {ingestionStatus === "failed" && ingestionError && (
            <div className="rounded-lg bg-red-100 border border-red-200 px-4 py-3">
              <p className="text-xs font-mono text-red-700">{ingestionError}</p>
            </div>
          )}

          {/* ID — only shown when ready */}
          {ingestionStatus === "completed" && (
            <div className="bg-white rounded-lg border border-emerald-200 px-4 py-3 space-y-1">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Example Set ID</p>
              <p className="text-sm font-mono font-semibold text-slate-800 select-all">{result.example_set_id}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
