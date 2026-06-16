import { apiUrl } from "../lib/api";

interface Props {
  downloadUrl: string;
  filename?: string;
}

export default function DownloadButton({ downloadUrl, filename }: Props) {
  return (
    <a href={apiUrl(downloadUrl)} download className="btn-primary px-6 py-3">
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      {filename ? (
        <span>
          Download <span className="font-mono text-[13px]">{filename}</span>
        </span>
      ) : (
        "Download IDML file"
      )}
    </a>
  );
}
