import { useRef, useState } from "react";

interface Props {
  label: string;
  accept: string;
  multiple?: boolean;
  files: File[];
  onChange: (files: File[]) => void;
}

function FileIcon({ ext }: { ext: string }) {
  const isIdml = ext.includes("idml");
  return (
    <div
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border ${
        isIdml ? "border-accent-400/20 bg-accent-500/10" : "border-emerald-400/20 bg-emerald-500/10"
      }`}
    >
      <svg
        className={`h-4 w-4 ${isIdml ? "text-accent-300" : "text-emerald-300"}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    </div>
  );
}

export default function FileDropzone({ label, accept, multiple = false, files, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      accept.split(",").some((ext) => f.name.toLowerCase().endsWith(ext.trim()))
    );
    onChange(multiple ? [...files, ...dropped] : dropped.slice(0, 1));
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    onChange(multiple ? [...files, ...selected] : selected.slice(0, 1));
    if (inputRef.current) inputRef.current.value = "";
  };

  const remove = (idx: number) => {
    onChange(files.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2.5">
      <label className="block text-sm font-semibold text-slate-200">{label}</label>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onClick={() => inputRef.current?.click()}
        role="button"
        aria-label={`Upload ${label}`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={`relative cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center backdrop-blur transition-all duration-200 ${
          dragActive
            ? "scale-[1.01] border-accent-400 bg-accent-500/10 shadow-glow-sm"
            : "border-white/15 bg-white/[0.03] hover:border-accent-400/40 hover:bg-accent-500/[0.04]"
        }`}
      >
        {/* Upload icon */}
        <div className="mb-3 flex justify-center">
          <div
            className={`flex h-11 w-11 items-center justify-center rounded-full border transition-colors ${
              dragActive ? "border-accent-400/40 bg-accent-500/15" : "border-white/10 bg-white/[0.05]"
            }`}
          >
            <svg
              className={`h-5 w-5 transition-colors ${dragActive ? "text-accent-300" : "text-slate-500"}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
        </div>

        <p className="text-sm text-slate-400">
          <span className="font-semibold text-accent-300">Browse files</span>
          {" "}or drag & drop
        </p>
        <p className="mt-1 font-mono text-xs text-slate-600">
          {accept.replace(/\./g, "").toUpperCase().replace(",", " · ")}
        </p>

        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          onChange={handleChange}
        />
      </div>

      {files.length > 0 && (
        <ul className="space-y-1.5">
          {files.map((f, i) => (
            <li
              key={i}
              className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 backdrop-blur"
            >
              <FileIcon ext={f.name} />
              <span className="flex-1 truncate text-sm font-medium text-slate-200">{f.name}</span>
              <span className="shrink-0 text-xs text-slate-500">
                {f.size > 1024 * 1024
                  ? `${(f.size / 1024 / 1024).toFixed(1)} MB`
                  : `${Math.round(f.size / 1024)} KB`}
              </span>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); remove(i); }}
                aria-label={`Remove ${f.name}`}
                className="ml-1 flex h-6 w-6 cursor-pointer items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-rose-500/10 hover:text-rose-400"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
