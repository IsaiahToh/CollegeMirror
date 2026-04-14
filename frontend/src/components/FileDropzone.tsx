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
    <div className={`w-8 h-8 rounded-md flex items-center justify-center shrink-0 ${isIdml ? "bg-indigo-100" : "bg-emerald-100"}`}>
      <svg className={`w-4 h-4 ${isIdml ? "text-indigo-600" : "text-emerald-600"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
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
      <label className="block text-sm font-semibold text-slate-700">{label}</label>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onClick={() => inputRef.current?.click()}
        role="button"
        aria-label={`Upload ${label}`}
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        className={`relative cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-all duration-150 ${
          dragActive
            ? "border-brand-500 bg-brand-50 scale-[1.01]"
            : "border-slate-200 bg-white hover:border-brand-400 hover:bg-slate-50"
        }`}
      >
        {/* Upload icon */}
        <div className="flex justify-center mb-3">
          <div className={`w-11 h-11 rounded-full flex items-center justify-center transition-colors ${dragActive ? "bg-brand-100" : "bg-slate-100"}`}>
            <svg className={`w-5 h-5 transition-colors ${dragActive ? "text-brand-600" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
        </div>

        <p className="text-sm text-slate-600">
          <span className="font-semibold text-brand-600">Browse files</span>
          {" "}or drag & drop
        </p>
        <p className="text-xs text-slate-400 mt-1 font-mono">{accept.replace(/\./g, "").toUpperCase().replace(",", " · ")}</p>

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
              className="flex items-center gap-3 bg-white border border-slate-200 rounded-lg px-3 py-2.5 shadow-card"
            >
              <FileIcon ext={f.name} />
              <span className="truncate flex-1 text-sm text-slate-700 font-medium">{f.name}</span>
              <span className="text-xs text-slate-400 shrink-0">
                {f.size > 1024 * 1024
                  ? `${(f.size / 1024 / 1024).toFixed(1)} MB`
                  : `${Math.round(f.size / 1024)} KB`}
              </span>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); remove(i); }}
                aria-label={`Remove ${f.name}`}
                className="ml-1 w-6 h-6 flex items-center justify-center rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
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
