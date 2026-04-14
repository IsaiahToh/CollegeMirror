interface Props {
  downloadUrl: string;
}

export default function DownloadButton({ downloadUrl }: Props) {
  return (
    <a
      href={downloadUrl}
      download
      className="inline-flex items-center gap-2.5 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg shadow-sm transition-all duration-150 hover:shadow-md cursor-pointer"
    >
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      Download IDML file
    </a>
  );
}
