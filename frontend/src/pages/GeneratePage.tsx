import { useState } from "react";
import FileDropzone from "../components/FileDropzone";
import JobStatus from "../components/JobStatus";
import { apiUrl } from "../lib/api";
import { loadExampleSetId } from "../lib/storage";

export default function GeneratePage() {
  const [wordFile, setWordFile] = useState<File[]>([]);
  const [exampleSetId, setExampleSetId] = useState(() => loadExampleSetId());
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [outputName, setOutputName] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = wordFile.length === 1 && exampleSetId.trim().length > 0 && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setJobId(null);

    const file = wordFile[0];
    const form = new FormData();
    form.append("word_file", file);

    try {
      const res = await fetch(
        apiUrl(`/generate?example_set_id=${encodeURIComponent(exampleSetId.trim())}`),
        { method: "POST", body: form }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      setJobId(data.job_id);
      // Mirrors the backend's download naming: {input-base}_generated.idml
      setOutputName(`${file.name.replace(/\.docx$/i, "")}_generated.idml`);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-10">
      {/* Page header */}
      <div className="animate-fade-up space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-accent-300">
          Step 02 — Generate
        </p>
        <h1 className="font-display text-4xl font-medium tracking-tight text-white md:text-5xl">
          New content, same spirit
        </h1>
        <p className="max-w-xl text-sm leading-relaxed text-slate-400">
          Upload a new Word document and CollegeMirror will generate an InDesign file styled after
          your trained examples — ready to review and finalise in Adobe InDesign.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="glass animate-fade-up divide-y divide-white/[0.06]" style={{ animationDelay: "120ms" }}>
          {/* Example Set ID */}
          <div className="space-y-2 p-5">
            <label htmlFor="example-set-id" className="block text-sm font-semibold text-slate-200">
              Example set ID
            </label>
            <p className="text-xs text-slate-500">
              From Step 1 — prefilled automatically after training completes on this device.
            </p>
            <input
              id="example-set-id"
              type="text"
              value={exampleSetId}
              onChange={(e) => setExampleSetId(e.target.value)}
              placeholder="e.g. exset_a1b2c3d4"
              className="glass-input font-mono"
            />
          </div>

          {/* Word doc upload */}
          <div className="p-5">
            <FileDropzone
              label="New Word document (.docx)"
              accept=".docx"
              multiple={false}
              files={wordFile}
              onChange={setWordFile}
            />
          </div>
        </div>

        {/* Submit */}
        <div className="animate-fade-up flex items-center justify-between" style={{ animationDelay: "220ms" }}>
          <p className="text-xs text-slate-500">
            Generation typically takes 30–90 seconds.
          </p>
          <button type="submit" disabled={!canSubmit} className="btn-primary">
            {loading ? (
              <>
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Starting…
              </>
            ) : (
              <>
                Generate InDesign file
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>
      </form>

      {error && (
        <div className="glass flex items-start gap-3 border-rose-400/30 p-4">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-rose-300">{error}</p>
        </div>
      )}

      {jobId && (
        <div className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
            <svg className="h-4 w-4 text-accent-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Generation progress
          </h2>
          <JobStatus jobId={jobId} outputName={outputName} />
          <p className="text-xs text-slate-500">
            Once complete, open the downloaded .idml in Adobe InDesign to review and finalise.
          </p>
        </div>
      )}
    </div>
  );
}
