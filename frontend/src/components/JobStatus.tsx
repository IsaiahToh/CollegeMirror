import { useEffect, useState } from "react";
import DownloadButton from "./DownloadButton";

interface JobState {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  example_set_id: string;
  warnings: string[];
  error: string | null;
  download_url: string | null;
}

interface Props {
  jobId: string;
}

const STATUS_CONFIG = {
  pending: {
    label: "Queued",
    description: "Waiting to start…",
    icon: (
      <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    badge: "bg-slate-100 text-slate-600",
    pulse: false,
  },
  running: {
    label: "Generating",
    description: "Claude is planning the layout and building your InDesign file…",
    icon: (
      <svg className="w-4 h-4 text-brand-600 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    ),
    badge: "bg-brand-100 text-brand-700",
    pulse: true,
  },
  completed: {
    label: "Complete",
    description: "Your InDesign file is ready to download.",
    icon: (
      <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    ),
    badge: "bg-emerald-100 text-emerald-700",
    pulse: false,
  },
  failed: {
    label: "Failed",
    description: "Something went wrong during generation.",
    icon: (
      <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    badge: "bg-red-100 text-red-700",
    pulse: false,
  },
};

export default function JobStatus({ jobId }: Props) {
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(`/jobs/${jobId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: JobState = await res.json();
        if (!cancelled) setJob(data);
        if (data.status === "pending" || data.status === "running") {
          setTimeout(poll, 3000);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    };

    poll();
    return () => { cancelled = true; };
  }, [jobId]);

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex items-start gap-3">
        <svg className="w-4 h-4 text-red-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm text-red-700">Polling error: {error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 flex items-center gap-3">
        <div className="w-4 h-4 rounded-full border-2 border-slate-300 border-t-brand-500 animate-spin" />
        <p className="text-sm text-slate-500">Loading job status…</p>
      </div>
    );
  }

  const cfg = STATUS_CONFIG[job.status] ?? STATUS_CONFIG.pending;

  return (
    <div className={`rounded-xl border bg-white shadow-card overflow-hidden ${
      job.status === "completed" ? "border-emerald-200" :
      job.status === "failed" ? "border-red-200" :
      "border-slate-200"
    }`}>
      {/* Status bar */}
      <div className={`px-5 py-4 flex items-center justify-between gap-4 ${
        job.status === "completed" ? "bg-emerald-50" :
        job.status === "failed" ? "bg-red-50" :
        "bg-slate-50"
      }`}>
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
            job.status === "completed" ? "bg-emerald-100" :
            job.status === "failed" ? "bg-red-100" :
            "bg-white border border-slate-200"
          }`}>
            {cfg.icon}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${cfg.badge}`}>
                {cfg.label}
              </span>
              {cfg.pulse && (
                <span className="flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-brand-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-500" />
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">{cfg.description}</p>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="px-5 py-4 space-y-4">
        <p className="text-xs text-slate-400 font-mono">
          Job <span className="text-slate-600">{job.job_id}</span>
        </p>

        {job.status === "completed" && job.download_url && (
          <DownloadButton downloadUrl={job.download_url} />
        )}

        {job.warnings.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-1.5">
            <div className="flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-xs font-semibold text-amber-700">{job.warnings.length} warning{job.warnings.length > 1 ? "s" : ""}</p>
            </div>
            <ul className="space-y-0.5">
              {job.warnings.map((w, i) => (
                <li key={i} className="text-xs text-amber-700 pl-5 list-disc">{w}</li>
              ))}
            </ul>
          </div>
        )}

        {job.status === "failed" && job.error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3">
            <p className="text-xs font-semibold text-red-700 mb-1">Error details</p>
            <p className="text-xs text-red-600 font-mono leading-relaxed">{job.error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
