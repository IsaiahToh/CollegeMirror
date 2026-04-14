import { useState } from "react";
import FileDropzone from "../components/FileDropzone";
import JobStatus from "../components/JobStatus";

export default function GeneratePage() {
  const [wordFile, setWordFile] = useState<File[]>([]);
  const [exampleSetId, setExampleSetId] = useState("");
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = wordFile.length === 1 && exampleSetId.trim().length > 0 && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setJobId(null);

    const form = new FormData();
    form.append("word_file", wordFile[0]);

    try {
      const res = await fetch(`/generate?example_set_id=${encodeURIComponent(exampleSetId.trim())}`, {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      setJobId(data.job_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Page header */}
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-xs font-semibold text-brand-600 uppercase tracking-wider mb-2">
          <span className="w-5 h-5 rounded-full bg-brand-100 flex items-center justify-center text-[10px] font-bold text-brand-700">2</span>
          Step two
        </div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Generate a new document</h1>
        <p className="text-sm text-slate-500 max-w-xl leading-relaxed">
          Upload a new Word document and CollegeMirror will generate an InDesign file styled after
          your trained examples — ready to review and finalise in Adobe InDesign.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white rounded-xl border border-slate-200 shadow-card divide-y divide-slate-100">
          {/* Example Set ID */}
          <div className="p-5 space-y-2">
            <label htmlFor="example-set-id" className="block text-sm font-semibold text-slate-700">
              Example set ID
            </label>
            <p className="text-xs text-slate-400">From Step 1 — paste the ID you received after training.</p>
            <input
              id="example-set-id"
              type="text"
              value={exampleSetId}
              onChange={(e) => setExampleSetId(e.target.value)}
              placeholder="e.g. exset_a1b2c3d4"
              className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm font-mono text-slate-800 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow"
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
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-400">
            Generation typically takes 30–90 seconds.
          </p>
          <button
            type="submit"
            disabled={!canSubmit}
            className="flex items-center gap-2 px-6 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-slate-200 disabled:text-slate-400 text-white text-sm font-semibold rounded-lg shadow-sm hover:shadow-md transition-all duration-150 cursor-pointer disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Starting…
              </>
            ) : (
              <>
                Generate InDesign file
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </>
            )}
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex items-start gap-3">
          <svg className="w-4 h-4 text-red-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {jobId && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <svg className="w-4 h-4 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Generation progress
          </h2>
          <JobStatus jobId={jobId} />
          <p className="text-xs text-slate-400">
            Once complete, open the downloaded .idml in Adobe InDesign to review and finalise.
          </p>
        </div>
      )}
    </div>
  );
}
