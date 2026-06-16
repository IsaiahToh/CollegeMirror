const EXAMPLE_SET_KEY = "collegemirror.exampleSetId";

export function saveExampleSetId(id: string): void {
  try {
    localStorage.setItem(EXAMPLE_SET_KEY, id);
  } catch {
    // storage unavailable (private mode etc.) — non-fatal
  }
}

export function loadExampleSetId(): string {
  try {
    return localStorage.getItem(EXAMPLE_SET_KEY) ?? "";
  } catch {
    return "";
  }
}
