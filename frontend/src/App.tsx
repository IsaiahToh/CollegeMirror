import { Link, Route, Routes, useLocation } from "react-router-dom";
import ExamplesPage from "./pages/ExamplesPage";
import GeneratePage from "./pages/GeneratePage";

function Nav() {
  const { pathname } = useLocation();

  const steps = [
    { href: "/", label: "Train", number: "01" },
    { href: "/generate", label: "Generate", number: "02" },
  ];

  return (
    <nav className="bg-navy-800 border-b border-white/10">
      <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Wordmark */}
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-brand-600 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <span className="text-white font-semibold text-[15px] tracking-tight">
            CollegeMirror
          </span>
        </div>

        {/* Step pills */}
        <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1">
          {steps.map((step, i) => {
            const active = pathname === step.href;
            return (
              <Link
                key={step.href}
                to={step.href}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${
                  active
                    ? "bg-brand-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white hover:bg-white/10"
                }`}
              >
                <span className={`text-[10px] font-bold tracking-widest ${active ? "text-brand-200" : "text-slate-500"}`}>
                  {step.number}
                </span>
                {step.label}
                {i < steps.length - 1 && !active && (
                  <svg className="w-3.5 h-3.5 text-slate-600 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Nav />
      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-10">
        <Routes>
          <Route path="/" element={<ExamplesPage />} />
          <Route path="/generate" element={<GeneratePage />} />
        </Routes>
      </main>
      <footer className="border-t border-slate-200 py-4">
        <p className="text-center text-xs text-slate-400">
          CollegeMirror — AI-powered InDesign document automation
        </p>
      </footer>
    </div>
  );
}
