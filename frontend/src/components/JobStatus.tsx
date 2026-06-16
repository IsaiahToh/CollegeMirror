import { useEffect, useState } from "react";
import { apiUrl } from "../lib/api";
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
  /** Expected output filename, shown on the download button when known. */
  outputName?: string;
}

const STATUS_CONFIG = {
  pending: {
    label: "Queued",
    description: "Waiting to start…",
    badge: "bg-white/[0.06] text-slate-300 border border-white/10",
    icon: (
      <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  running: {
    label: "Generating",
    description: "Claude is planning the layout and building your InDesign file…",
    badge: "bg-accent-500/15 text-accent-300 border border-accent-400/25",
    icon: (
      <svg className="h-4 w-4 animate-spin text-accent-400" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    ),
  },
  completed: {
    label: "Complete",
    description: "Your InDesign file is ready to download.",
    badge: "bg-emerald-500/15 text-emerald-300 border border-emerald-400/25",
    icon: (
      <svg className="h-4 w-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    ),
  },
  failed: {
    label: "Failed",
    description: "Something went wrong during generation.",
    badge: "bg-rose-500/15 text-rose-300 border border-rose-400/25",
    icon: (
      <svg className="h-4 w-4 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
  },
};

export default function JobStatus({ jobId, outputName }: Props) {
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(apiUrl(`/jobs/${jobId}`));
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
      <div className="glass flex items-start gap-3 border-rose-400/30 p-4">
        <svg className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm text-rose-300">Polling error: {error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="glass flex items-center gap-3 p-5">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/15 border-t-accent-400" />
        <p className="text-sm text-slate-400">Loading job status…</p>
      </div>
    );
  }

  const cfg = STATUS_CONFIG[job.status] ?? STATUS_CONFIG.pending;
  const inProgress = job.status === "pending" || job.status === "running";

  return (
    <div
      className={`glass overflow-hidden ${
        job.status === "completed" ? "border-emerald-400/30" :
        job.status === "failed" ? "border-rose-400/30" :
        ""
      }`}
    >
      {/* Status header */}
      <div className="flex items-center justify-between gap-4 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.05]">
            {cfg.icon}
          </div>
          <div>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${cfg.badge}`}>
              {cfg.label}
            </span>
            <p className="mt-1 text-xs text-slate-400">{cfg.description}</p>
          </div>
        </div>
      </div>

      {/* Shimmer progress while queued/generating */}
      {inProgress && (
        <div className="mx-5 h-1 overflow-hidden rounded-full bg-white/[0.06]">
          <div className="animate-shimmer h-full w-1/3 bg-gradient-to-r from-transparent via-accent-400 to-transparent" />
        </div>
      )}

      {/* Body */}
      <div className="space-y-4 px-5 py-4">
        <p className="font-mono text-xs text-slate-500">
          Job <span className="text-slate-300">{job.job_id}</span>
        </p>

        {job.status === "completed" && job.download_url && (
          <DownloadButton downloadUrl={job.download_url} filename={outputName} />
        )}

        {job.warnings.length > 0 && (
          <div className="space-y-1.5 rounded-xl border border-amber-400/25 bg-amber-500/[0.08] p-3">
            <div className="flex items-center gap-1.5">
              <svg className="h-3.5 w-3.5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-xs font-semibold text-amber-300">
                {job.warnings.length} warning{job.warnings.length > 1 ? "s" : ""}
              </p>
            </div>
            <ul className="space-y-0.5">
              {job.warnings.map((w, i) => (
                <li key={i} className="list-disc pl-5 text-xs text-amber-200/90">{w}</li>
              ))}
            </ul>
          </div>
        )}

        {job.status === "failed" && job.error && (
          <div className="rounded-xl border border-rose-400/25 bg-rose-500/[0.08] p-3">
            <p className="mb-1 text-xs font-semibold text-rose-300">Error details</p>
            <p className="font-mono text-xs leading-relaxed text-rose-200/90">{job.error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
