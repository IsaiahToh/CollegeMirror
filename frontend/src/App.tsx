import { Link, Route, Routes, useLocation } from "react-router-dom";
import ExamplesPage from "./pages/ExamplesPage";
import GeneratePage from "./pages/GeneratePage";

/** Slow-drifting aurora blobs + film grain, fixed behind all content. */
function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
      <div
        className="aurora-blob animate-drift-a -left-40 -top-40 h-[34rem] w-[34rem]"
        style={{ background: "radial-gradient(circle, rgba(34,200,230,0.16), transparent 65%)" }}
      />
      <div
        className="aurora-blob animate-drift-b -right-52 top-1/3 h-[40rem] w-[40rem]"
        style={{ background: "radial-gradient(circle, rgba(91,84,255,0.13), transparent 65%)" }}
      />
      <div
        className="aurora-blob animate-drift-c -bottom-56 left-1/4 h-[36rem] w-[36rem]"
        style={{ background: "radial-gradient(circle, rgba(255,184,104,0.07), transparent 65%)" }}
      />
      <div className="grain absolute inset-0" />
    </div>
  );
}

function Nav() {
  const { pathname } = useLocation();

  const steps = [
    { href: "/", label: "Train", number: "01" },
    { href: "/generate", label: "Generate", number: "02" },
  ];

  return (
    <header className="sticky top-0 z-40 px-4 pt-4">
      <nav className="glass mx-auto flex h-14 max-w-5xl items-center justify-between px-5">
        {/* Wordmark */}
        <Link to="/" className="flex items-center gap-3 rounded-lg">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 shadow-glow-sm">
            <svg className="h-4 w-4 text-ink-950" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <span className="font-display text-lg font-medium tracking-tight text-white">
            CollegeMirror
          </span>
        </Link>

        {/* Step pills — glass segmented control */}
        <div className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] p-1">
          {steps.map((step) => {
            const active = pathname === step.href;
            return (
              <Link
                key={step.href}
                to={step.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition-all duration-200 ${
                  active
                    ? "bg-accent-500 text-ink-950 shadow-glow-sm"
                    : "text-slate-400 hover:bg-white/[0.07] hover:text-white"
                }`}
              >
                <span className={`text-[10px] font-bold tracking-widest ${active ? "text-ink-800" : "text-slate-600"}`}>
                  {step.number}
                </span>
                {step.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}

export default function App() {
  return (
    <div className="relative flex min-h-screen flex-col">
      <Backdrop />
      <Nav />
      <main className="relative mx-auto w-full max-w-5xl flex-1 px-6 py-12">
        <Routes>
          <Route path="/" element={<ExamplesPage />} />
          <Route path="/generate" element={<GeneratePage />} />
        </Routes>
      </main>
      <footer className="relative py-6">
        <p className="text-center text-xs tracking-wide text-slate-600">
          CollegeMirror — AI-powered InDesign document automation
        </p>
      </footer>
    </div>
  );
}
