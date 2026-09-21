# Sanad Stage C — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single screen that takes pasted text and shows each quotation traced back to its source — or visibly failing to be — with every verdict coming from the Stage A Python engine.

**Architecture:** A React + Vite + TypeScript static build and the existing FastAPI service deploy as one Vercel project, sharing an origin so there is no CORS. The TypeScript API client is generated from the API's own OpenAPI schema and CI fails if the committed copy drifts. No verification logic exists in the frontend.

**Tech Stack:** React 18, Vite 5, TypeScript 5, Vitest + Testing Library, Motion (framer-motion), `openapi-typescript` for client generation, Amiri / Spectral / IBM Plex Mono via `@fontsource`.

**Spec:** `docs/superpowers/specs/2026-09-20-stage-c-frontend-design.md`

## Global Constraints

- **No verification logic in `web/`.** Not a pre-check, not a shortcut, not a heuristic. Every verdict is read from the API response. A second verifier that can disagree with the first is the defect this project spent Stage A hunting.
- **The user's text is marked, never rewritten.** Never substitute the corpus reading for what the user typed.
- **No verdict is distinguished by colour alone.** Every verdict carries a distinct glyph, a text label, and a distinct chain state.
- **`NOT_FOUND` always renders its corpus-scope caveat inline**, attached to the verdict, never in a page footer.
- **`PERSONAL_RULING` renders no verdict at all** — the handoff card replaces the evidence stack. Not a verdict with a caution attached.
- **`prefers-reduced-motion` is fully honoured.** Motion draws attention to a verdict; it never encodes one.
- **Canonical Arabic is rendered byte-identical to the API response.** No normalization, no NFC pass, no re-spacing. `text_ar` is verbatim Tanzil under CC BY 3.0.
- `web/src/api/client.ts` and `types.ts` are **generated** — never hand-edited.
- Node 20, npm 10. TypeScript `strict: true`.

### Design tokens (fixed — do not invent alternatives)

```css
--page:      #E6E8E6;  /* cool grey-green paper. NOT cream — see spec §5.3 */
--ink:       #241F1C;  /* iron gall brown-black, warm against the cool page */
--rubric:    #9E2B25;  /* cinnabar: marks a break in the chain, scribal convention */
--verdigris: #2F6B5E;  /* copper green: verified */
--gold:      #A8842C;  /* used once — the rosette terminating a complete chain */
```

Type roles: **Amiri** (Arabic, all canonical text), **Spectral** (Latin body), **IBM Plex Mono** (checksums, tiers, scores, record ids). All SIL OFL.

### API response shape (measured from `/openapi.json`, 2026-09-20)

```
VerifyResponse  { quotations[], claims[], risk, requires_handoff, overall, corpus_scope }
QuotationOut    { quoted_text, start, end, verdict, tier, score, record, given_reference, diff, also_at }
RecordOut       { id, reference_display, text_ar, text_ar_sha256, surah, ayah,
                  translation_en, translation_disclaimer }
ClaimOut        { kind, label, note }
```

`verdict` is one of `EXACT`, `EXACT_ORTHOGRAPHY`, `NEAR_MATCH`, `WRONG_REFERENCE`, `NOT_FOUND`.
`tier` is `light`, `standard`, `aggressive`, or null.
`diff` is `[["equal"|"quoted-only"|"corpus-only", string], ...]` or null.

---

## File Structure

```
web/
  package.json, tsconfig.json, vite.config.ts, index.html
  src/
    main.tsx                 mount
    App.tsx                  routes between Verify and Provenance
    api/client.ts            GENERATED — fetch wrappers
    api/types.ts             GENERATED — response types
    api/useVerify.ts         request state machine: idle/loading/ok/unreachable/error
    theme/tokens.css         the five tokens, type scale, fonts
    components/
      VerdictBadge.tsx       glyph + label + state. Colour-independent.
      CharDiff.tsx           renders QuotationOut.diff
      IsnadTrace.tsx         the chain. One per quotation.
      EvidenceCard.tsx       verdict header + trace + diff + caveat
      MarkedText.tsx         the user's text with spans marked in place
      ClaimList.tsx          ClaimOut[] rendering
      HandoffCard.tsx        replaces the stack on PERSONAL_RULING
      ErrorState.tsx         unreachable / server error / no-arabic / empty
      ProvenancePanel.tsx    GET /api/corpus rendered
    screens/Verify.tsx
  tests/…                    mirrors src/
app.py                       Vercel Python entrypoint (repo root)
vercel.json                  routing + excludeFiles
```

---

### Task 1: Scaffold `web/`, generate the API client, wire CI

Scaffolding folds in here because nothing else can start without it.

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`
- Create: `web/scripts/generate-client.sh`
- Create: `web/src/api/types.ts` (generated), `web/src/api/client.ts`
- Test: `web/tests/api/client.test.ts`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `apiFetch<T>(path: string, init?: RequestInit): Promise<T>`; `verify(text: string): Promise<VerifyResponse>`; `getCorpus(): Promise<CorpusResponse>`; all types in `api/types.ts`.

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "sanad-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "generate:client": "sh scripts/generate-client.sh",
    "lint:types": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "motion": "^11.11.0",
    "@fontsource/amiri": "^5.1.0",
    "@fontsource/spectral": "^5.1.0",
    "@fontsource/ibm-plex-mono": "^5.1.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.2",
    "jsdom": "^25.0.1",
    "openapi-typescript": "^7.4.1",
    "typescript": "^5.6.3",
    "vite": "^5.4.9",
    "vitest": "^2.1.3"
  }
}
```

- [ ] **Step 2: Create `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: Create `web/vite.config.ts`**

`/api` proxies to the local FastAPI in development. In production they share an origin, so the proxy is a dev-only convenience.

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  build: { outDir: "dist", sourcemap: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
});
```

- [ ] **Step 4: Create `web/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Sanad — quotation verification</title>
    <meta name="description" content="Check whether a Qur'anic quotation is genuinely in the corpus, and see the chain back to its source." />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `web/tests/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 6: Create `web/scripts/generate-client.sh`**

```sh
#!/bin/sh
# Regenerate the typed API client from the running API's OpenAPI schema.
# Start the API first:  .venv/bin/uvicorn sanad.api.app:create_app --factory --port 8000
set -e
URL="${SANAD_OPENAPI_URL:-http://localhost:8000/openapi.json}"
npx openapi-typescript "$URL" -o src/api/types.ts
echo "wrote src/api/types.ts from $URL"
```

- [ ] **Step 7: Generate the types**

From the repository root, start the API and generate:

```bash
SANAD_AUDIT_DB=/tmp/sanad-audit.db \
  .venv/bin/uvicorn sanad.api.app:create_app --factory --port 8000 &
sleep 3
cd web && npm install && npm run generate:client
kill %1
```

Confirm `web/src/api/types.ts` exists and contains `VerifyResponse`, `QuotationOut`, `RecordOut`, `ClaimOut`.

- [ ] **Step 8: Write the failing test**

Create `web/tests/api/client.test.ts`:

```ts
import { describe, expect, it, vi, afterEach } from "vitest";
import { apiFetch, ApiUnreachable, ApiError } from "../../src/api/client";

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("returns parsed json on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    ));
    await expect(apiFetch<{ ok: boolean }>("/api/health")).resolves.toEqual({ ok: true });
  });

  it("throws ApiUnreachable when the network fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));
    await expect(apiFetch("/api/health")).rejects.toBeInstanceOf(ApiUnreachable);
  });

  it("throws ApiError carrying the status on a 5xx", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 503 })));
    await expect(apiFetch("/api/health")).rejects.toMatchObject({ status: 503 });
  });

  it("throws ApiError on a 422 so validation is distinguishable from unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: [] }), { status: 422 })
    ));
    await expect(apiFetch("/api/verify")).rejects.toBeInstanceOf(ApiError);
  });
});
```

- [ ] **Step 9: Run it and confirm it fails**

Run: `cd web && npx vitest run tests/api/client.test.ts`
Expected: FAIL — cannot resolve `../../src/api/client`.

- [ ] **Step 10: Implement `web/src/api/client.ts`**

```ts
import type { components } from "./types";

export type VerifyResponse = components["schemas"]["VerifyResponse"];
export type QuotationOut = components["schemas"]["QuotationOut"];
export type RecordOut = components["schemas"]["RecordOut"];
export type ClaimOut = components["schemas"]["ClaimOut"];

/** The API could not be reached at all. Distinct from an error it returned. */
export class ApiUnreachable extends Error {
  constructor(cause?: unknown) {
    super("Cannot reach the verifier.");
    this.name = "ApiUnreachable";
    this.cause = cause;
  }
}

/** The API answered, with a status we cannot use. */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, body: string) {
    super(`The verifier returned ${status}.`);
    this.name = "ApiError";
    this.status = status;
    this.cause = body;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (cause) {
    throw new ApiUnreachable(cause);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await response.text().catch(() => ""));
  }
  return (await response.json()) as T;
}

export function verify(text: string): Promise<VerifyResponse> {
  return apiFetch<VerifyResponse>("/api/verify", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export interface CorpusSource {
  id: string;
  kind: string;
  title: string;
  publisher: string | null;
  edition: string | null;
  url: string;
  license_id: string;
  license_url: string | null;
  attribution: string;
  retrieved_at: string;
  upstream_sha256: string;
  modifications: string;
}

export interface CorpusResponse {
  db_sha256: string;
  db_path: string;
  stats: { records: number; sources: number; translations: number };
  scope: string;
  sources: CorpusSource[];
}

export function getCorpus(): Promise<CorpusResponse> {
  return apiFetch<CorpusResponse>("/api/corpus");
}
```

- [ ] **Step 11: Run tests, confirm they pass**

Run: `cd web && npx vitest run tests/api/client.test.ts`
Expected: PASS, 4 tests.

- [ ] **Step 12: Minimal `main.tsx` and `App.tsx` so the build succeeds**

`web/src/main.tsx`:
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./theme/tokens.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode><App /></StrictMode>
);
```

`web/src/App.tsx`:
```tsx
export default function App() {
  return <main>Sanad</main>;
}
```

Create an empty `web/src/theme/tokens.css` for now; Task 2 fills it.

- [ ] **Step 13: Add the CI job**

In `.github/workflows/ci.yml`, add a job alongside the existing one:

```yaml
  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: npm ci
        working-directory: web
      - run: npm run lint:types
        working-directory: web
      - run: npm test
        working-directory: web
      - run: npm run build
        working-directory: web

      # The generated client must match the API it is generated from.
      # Stage A shipped ten defects of one shape: two things meant to agree,
      # quietly diverging, with every test still passing. This is the check
      # that makes that impossible here.
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -e ".[dev]"
      - name: Regenerate the API client and fail on drift
        run: |
          SANAD_AUDIT_DB=/tmp/audit.db \
            uvicorn sanad.api.app:create_app --factory --port 8000 &
          for i in $(seq 1 30); do
            curl -sf http://localhost:8000/api/health >/dev/null && break || sleep 1
          done
          cd web && npm run generate:client
          git diff --exit-code src/api/types.ts \
            || { echo "::error::src/api/types.ts is stale. Run 'npm run generate:client' and commit."; exit 1; }
```

- [ ] **Step 14: Commit**

```bash
git add web .github/workflows/ci.yml
git commit -m "feat(web): scaffold Vite app with a generated API client

The TypeScript types come from the API's own OpenAPI schema and CI fails
if the committed copy drifts. Stage A shipped ten defects of one shape —
two things meant to agree, quietly diverging, with every test still
passing. A hand-written API type is that bug waiting in a new place."
```

---

### Task 2: Design tokens and Arabic typography

**Files:**
- Modify: `web/src/theme/tokens.css`
- Create: `web/tests/theme/tokens.test.tsx`

**Interfaces:**
- Produces: CSS custom properties `--page --ink --rubric --verdigris --gold`, type scale variables, and the classes `.arabic` (Amiri, RTL, large) and `.data` (IBM Plex Mono).

- [ ] **Step 1: Write the failing test**

Create `web/tests/theme/tokens.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import "../../src/theme/tokens.css";

describe("Arabic typography", () => {
  it("marks Arabic text with dir=rtl and lang=ar so it renders correctly", () => {
    render(<span className="arabic" dir="rtl" lang="ar" data-testid="a">قُلْ هُوَ ٱللَّهُ أَحَدٌ</span>);
    const el = screen.getByTestId("a");
    expect(el).toHaveAttribute("dir", "rtl");
    expect(el).toHaveAttribute("lang", "ar");
  });

  it("renders canonical Arabic byte-identical to its input", () => {
    // text_ar is verbatim Tanzil under CC BY 3.0 — no normalization anywhere.
    const canonical = "قُلْ هُوَ ٱللَّهُ أَحَدٌ";
    render(<span className="arabic" data-testid="b">{canonical}</span>);
    expect(screen.getByTestId("b").textContent).toBe(canonical);
    expect(screen.getByTestId("b").textContent).not.toBe(canonical.normalize("NFC"));
  });
});
```

Note the second assertion: Tanzil emits SHADDA before FATHA, which is **not** canonical NFC order. If anything in the render path normalizes, that assertion fails — which is the point.

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd web && npx vitest run tests/theme/tokens.test.tsx`
Expected: FAIL — `tokens.css` has no `.arabic` class yet, and the second assertion will surface any normalization.

- [ ] **Step 3: Implement `web/src/theme/tokens.css`**

```css
@import "@fontsource/amiri/400.css";
@import "@fontsource/amiri/700.css";
@import "@fontsource/spectral/400.css";
@import "@fontsource/spectral/600.css";
@import "@fontsource/ibm-plex-mono/400.css";

:root {
  /* Manuscript pigments. Cool paper, not cream — this is an instrument,
     not a facsimile. See the Stage A spec §10. */
  --page:      #E6E8E6;
  --ink:       #241F1C;
  --rubric:    #9E2B25;  /* red is apparatus in manuscript, not alarm */
  --verdigris: #2F6B5E;
  --gold:      #A8842C;  /* used once: the rosette on a complete chain */

  --ink-60: color-mix(in srgb, var(--ink) 60%, var(--page));
  --ink-30: color-mix(in srgb, var(--ink) 30%, var(--page));
  --ink-12: color-mix(in srgb, var(--ink) 12%, var(--page));

  --serif: "Spectral", Georgia, serif;
  --naskh: "Amiri", "Noto Naskh Arabic", serif;
  --mono:  "IBM Plex Mono", ui-monospace, monospace;

  --step--1: 0.833rem;
  --step-0:  1rem;
  --step-1:  1.2rem;
  --step-2:  1.44rem;
  --step-3:  1.728rem;

  --measure: 62ch;
  --rule: 1px solid var(--ink-12);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--page);
  color: var(--ink);
  font-family: var(--serif);
  font-size: var(--step-0);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

/* Canonical Qur'an text. Set large so diacritics are legible — this is a
   requirement, not a preference: the product asks people to compare
   individual marks. */
.arabic {
  font-family: var(--naskh);
  font-size: var(--step-3);
  line-height: 2.1;
  direction: rtl;
  text-align: right;
  font-feature-settings: "calt" 1, "liga" 1;
}

.data {
  font-family: var(--mono);
  font-size: var(--step--1);
  letter-spacing: -0.01em;
  color: var(--ink-60);
}

:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd web && npx vitest run tests/theme/tokens.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/theme/tokens.css web/tests/theme/tokens.test.tsx
git commit -m "feat(web): manuscript pigment tokens and Arabic typography

Cool grey-green paper rather than the cream that Islamic content is
universally rendered in. The spec calls this an instrument, not a
facsimile, and the palette follows: iron gall ink, cinnabar for a break
in the chain because red is apparatus in manuscript convention, verdigris
for verified, gold used exactly once on the rosette.

Canonical Arabic is set large enough that diacritics are legible, and a
test pins that it renders byte-identical — Tanzil emits SHADDA before
FATHA, which is not NFC order, so any normalization in the render path
fails that assertion."
```

---

### Task 3: `VerdictBadge` — colour-independent verdict rendering

**Files:**
- Create: `web/src/components/VerdictBadge.tsx`
- Test: `web/tests/components/VerdictBadge.test.tsx`

**Interfaces:**
- Consumes: nothing.
- Produces: `VerdictBadge({ verdict }: { verdict: Verdict })`; `type Verdict = "EXACT" | "EXACT_ORTHOGRAPHY" | "NEAR_MATCH" | "WRONG_REFERENCE" | "NOT_FOUND"`; `VERDICT_META: Record<Verdict, { glyph: string; label: string; tone: "verified" | "broken" | "absent" }>`.

- [ ] **Step 1: Write the failing test**

Create `web/tests/components/VerdictBadge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VerdictBadge, VERDICT_META, type Verdict } from "../../src/components/VerdictBadge";

const ALL: Verdict[] = ["EXACT", "EXACT_ORTHOGRAPHY", "NEAR_MATCH", "WRONG_REFERENCE", "NOT_FOUND"];

describe("VerdictBadge", () => {
  it.each(ALL)("renders a text label for %s", (v) => {
    render(<VerdictBadge verdict={v} />);
    expect(screen.getByText(VERDICT_META[v].label)).toBeInTheDocument();
  });

  it("gives every verdict a distinct glyph, so colour is never the only signal", () => {
    const glyphs = ALL.map((v) => VERDICT_META[v].glyph);
    expect(new Set(glyphs).size).toBe(ALL.length);
  });

  it("gives every verdict a distinct label", () => {
    const labels = ALL.map((v) => VERDICT_META[v].label);
    expect(new Set(labels).size).toBe(ALL.length);
  });

  it("exposes the verdict to assistive technology, not just visually", () => {
    render(<VerdictBadge verdict="NEAR_MATCH" />);
    expect(screen.getByRole("status")).toHaveTextContent(/near match/i);
  });

  it("never labels a NEAR_MATCH as verified", () => {
    expect(VERDICT_META.NEAR_MATCH.tone).not.toBe("verified");
    expect(VERDICT_META.NEAR_MATCH.label.toLowerCase()).not.toContain("verified");
  });

  it("marks only the two exact verdicts as verified", () => {
    const verified = ALL.filter((v) => VERDICT_META[v].tone === "verified");
    expect(verified.sort()).toEqual(["EXACT", "EXACT_ORTHOGRAPHY"]);
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd web && npx vitest run tests/components/VerdictBadge.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `web/src/components/VerdictBadge.tsx`**

```tsx
export type Verdict =
  | "EXACT"
  | "EXACT_ORTHOGRAPHY"
  | "NEAR_MATCH"
  | "WRONG_REFERENCE"
  | "NOT_FOUND";

/**
 * Every verdict carries a glyph AND a label AND a tone. Colour is never the
 * only signal — the gap between "verified" and "near match" is too
 * consequential to encode as a hue a reader may not distinguish.
 */
export const VERDICT_META: Record<
  Verdict,
  { glyph: string; label: string; tone: "verified" | "broken" | "absent" }
> = {
  EXACT:             { glyph: "۝", label: "Verified",                tone: "verified" },
  EXACT_ORTHOGRAPHY: { glyph: "۞", label: "Verified, spelling differs", tone: "verified" },
  NEAR_MATCH:        { glyph: "†", label: "Near match",              tone: "broken" },
  WRONG_REFERENCE:   { glyph: "‡", label: "Wrong reference",         tone: "broken" },
  NOT_FOUND:         { glyph: "○", label: "Not in this corpus",      tone: "absent" },
};

const TONE_COLOUR = {
  verified: "var(--verdigris)",
  broken: "var(--rubric)",
  absent: "var(--ink-60)",
} as const;

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const meta = VERDICT_META[verdict];
  return (
    <span
      role="status"
      data-verdict={verdict}
      data-tone={meta.tone}
      style={{
        display: "inline-flex",
        alignItems: "baseline",
        gap: "0.5ch",
        color: TONE_COLOUR[meta.tone],
        fontFamily: "var(--mono)",
        fontSize: "var(--step--1)",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
      }}
    >
      <span aria-hidden="true" style={{ fontSize: "var(--step-1)" }}>{meta.glyph}</span>
      {meta.label}
    </span>
  );
}
```

The glyphs are Qur'anic and scribal marks, not generic icons: U+06DD END OF AYAH for a complete chain, U+06DE START OF RUB EL HIZB for a complete chain with an orthographic note, dagger and double-dagger for scribal correction marks, and an open circle for absence.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd web && npx vitest run tests/components/VerdictBadge.test.tsx`
Expected: PASS, 10 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/VerdictBadge.tsx web/tests/components/VerdictBadge.test.tsx
git commit -m "feat(web): colour-independent verdict badge

Glyph, label and tone are all distinct per verdict, and tests pin that
no two share either. The difference between verified and near match is
too consequential to carry in a hue alone."
```

---

### Task 4: `CharDiff` — showing exactly which letters differ

**Files:**
- Create: `web/src/components/CharDiff.tsx`
- Test: `web/tests/components/CharDiff.test.tsx`

**Interfaces:**
- Consumes: `QuotationOut["diff"]` — `[["equal"|"quoted-only"|"corpus-only", string], ...] | null`.
- Produces: `CharDiff({ diff }: { diff: DiffOp[] | null })`; `type DiffOp = [string, string]`.

- [ ] **Step 1: Write the failing test**

Create `web/tests/components/CharDiff.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CharDiff } from "../../src/components/CharDiff";

describe("CharDiff", () => {
  it("renders nothing when there is no diff", () => {
    const { container } = render(<CharDiff diff={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("marks what you wrote and what the corpus has, distinctly", () => {
    render(<CharDiff diff={[["equal", "قل هو الله "], ["quoted-only", "احدق"], ["corpus-only", "احد"]]} />);
    expect(screen.getByTestId("quoted-only-0")).toHaveTextContent("احدق");
    expect(screen.getByTestId("corpus-only-0")).toHaveTextContent("احد");
  });

  it("labels each side in words, not by colour", () => {
    render(<CharDiff diff={[["quoted-only", "x"], ["corpus-only", "y"]]} />);
    expect(screen.getByText(/you wrote/i)).toBeInTheDocument();
    expect(screen.getByText(/corpus has/i)).toBeInTheDocument();
  });

  it("renders equal runs without marking them", () => {
    render(<CharDiff diff={[["equal", "قل هو"]]} />);
    expect(screen.queryByTestId("quoted-only-0")).toBeNull();
    expect(screen.queryByTestId("corpus-only-0")).toBeNull();
  });

  it("preserves the diff text byte-for-byte", () => {
    const seg = "ٱللَّهُ";
    render(<CharDiff diff={[["equal", seg]]} />);
    expect(screen.getByTestId("diff").textContent).toContain(seg);
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd web && npx vitest run tests/components/CharDiff.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `web/src/components/CharDiff.tsx`**

```tsx
export type DiffOp = [string, string];

/**
 * Renders the character-level difference between what the user wrote and what
 * the corpus holds. Both sides are labelled in words: a reader must be able to
 * tell which is which without relying on colour.
 */
export function CharDiff({ diff }: { diff: DiffOp[] | null }) {
  if (!diff || diff.length === 0) return null;

  let quotedIndex = 0;
  let corpusIndex = 0;

  return (
    <div data-testid="diff" style={{ marginBlockStart: "0.75rem" }}>
      <p className="data" style={{ margin: "0 0 0.25rem" }}>
        <span style={{ color: "var(--rubric)" }}>you wrote</span>
        {" · "}
        <span style={{ color: "var(--verdigris)" }}>corpus has</span>
      </p>
      <p className="arabic" dir="rtl" lang="ar" style={{ margin: 0, fontSize: "var(--step-2)" }}>
        {diff.map(([kind, text], i) => {
          if (kind === "equal") return <span key={i}>{text}</span>;
          if (kind === "quoted-only") {
            return (
              <span
                key={i}
                data-testid={`quoted-only-${quotedIndex++}`}
                style={{
                  color: "var(--rubric)",
                  textDecoration: "underline wavy var(--rubric)",
                  textUnderlineOffset: "0.35em",
                }}
              >
                {text}
              </span>
            );
          }
          return (
            <span
              key={i}
              data-testid={`corpus-only-${corpusIndex++}`}
              style={{
                color: "var(--verdigris)",
                borderBottom: "2px solid var(--verdigris)",
              }}
            >
              {text}
            </span>
          );
        })}
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd web && npx vitest run tests/components/CharDiff.test.tsx`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/CharDiff.tsx web/tests/components/CharDiff.test.tsx
git commit -m "feat(web): character-level diff with both sides named in words"
```

---

### Task 5: `IsnadTrace` — the signature element

**Files:**
- Create: `web/src/components/IsnadTrace.tsx`
- Test: `web/tests/components/IsnadTrace.test.tsx`

**Interfaces:**
- Consumes: `QuotationOut`, `VerdictBadge`'s `Verdict` and `VERDICT_META`.
- Produces: `IsnadTrace({ quotation, source }: { quotation: QuotationOut; source?: { license_id: string; title: string } | null })`.

The chain has five links in fixed order: **you quoted → normalized → matched → you cited → source & licence.** The rule governing all of it: the chain either completes or it visibly breaks, and you can see which link failed.

- [ ] **Step 1: Write the failing test**

Create `web/tests/components/IsnadTrace.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { IsnadTrace } from "../../src/components/IsnadTrace";
import type { QuotationOut } from "../../src/api/client";

const base: QuotationOut = {
  quoted_text: "قُلْ هُوَ ٱللَّهُ أَحَدٌ",
  start: 0, end: 20, verdict: "EXACT", tier: "light", score: 1,
  record: {
    id: "quran:112:1", reference_display: "Al-Ikhlas 112:1",
    text_ar: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", text_ar_sha256: "abc123", surah: 112, ayah: 1,
    translation_en: "Say: He is Allah, the One!", translation_disclaimer: "No translation…",
  },
  given_reference: null, diff: null, also_at: [],
} as unknown as QuotationOut;

const q = (over: Partial<QuotationOut>) => ({ ...base, ...over }) as QuotationOut;

describe("IsnadTrace", () => {
  it("renders all five links in order", () => {
    render(<IsnadTrace quotation={base} />);
    const links = screen.getAllByTestId(/^link-/).map((e) => e.getAttribute("data-testid"));
    expect(links).toEqual(["link-quoted", "link-normalized", "link-matched", "link-cited", "link-source"]);
  });

  it("completes the chain on EXACT", () => {
    render(<IsnadTrace quotation={base} />);
    expect(screen.getByTestId("chain")).toHaveAttribute("data-state", "complete");
  });

  it("breaks at the text link on NEAR_MATCH", () => {
    render(<IsnadTrace quotation={q({ verdict: "NEAR_MATCH", tier: "aggressive", score: 0.93 })} />);
    expect(screen.getByTestId("chain")).toHaveAttribute("data-state", "broken");
    expect(screen.getByTestId("link-matched")).toHaveAttribute("data-broken", "true");
  });

  it("breaks at the citation link on WRONG_REFERENCE, leaving the text link intact", () => {
    render(<IsnadTrace quotation={q({ verdict: "WRONG_REFERENCE", given_reference: "2:255" })} />);
    expect(screen.getByTestId("link-matched")).toHaveAttribute("data-broken", "false");
    expect(screen.getByTestId("link-cited")).toHaveAttribute("data-broken", "true");
  });

  it("terminates early on NOT_FOUND and shows no matched record", () => {
    render(<IsnadTrace quotation={q({ verdict: "NOT_FOUND", record: null, tier: null, score: 0 })} />);
    expect(screen.getByTestId("chain")).toHaveAttribute("data-state", "terminated");
    expect(screen.getByTestId("link-matched")).toHaveTextContent(/no match/i);
  });

  it("reports the tier that produced the match", () => {
    render(<IsnadTrace quotation={q({ verdict: "EXACT_ORTHOGRAPHY", tier: "standard" })} />);
    expect(screen.getByTestId("link-normalized")).toHaveTextContent("standard");
  });

  it("discloses other locations when the verse is repeated", () => {
    render(<IsnadTrace quotation={q({ also_at: ["quran:55:16", "quran:55:18"] })} />);
    expect(screen.getByTestId("link-matched")).toHaveTextContent(/also appears at 2 other/i);
  });

  it("says nothing about other locations when the verse is unique", () => {
    render(<IsnadTrace quotation={base} />);
    expect(screen.getByTestId("link-matched")).not.toHaveTextContent(/also appears/i);
  });

  it("shows the citation the user gave when one was found", () => {
    render(<IsnadTrace quotation={q({ verdict: "WRONG_REFERENCE", given_reference: "Al-Baqarah 2:255" })} />);
    expect(screen.getByTestId("link-cited")).toHaveTextContent("Al-Baqarah 2:255");
  });

  it("says no citation was given when none was", () => {
    render(<IsnadTrace quotation={base} />);
    expect(screen.getByTestId("link-cited")).toHaveTextContent(/no citation given/i);
  });

  it("renders the quoted text byte-identical to the input", () => {
    const canonical = "قُلْ هُوَ";
    render(<IsnadTrace quotation={q({ quoted_text: canonical })} />);
    expect(screen.getByTestId("link-quoted").textContent).toContain(canonical);
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd web && npx vitest run tests/components/IsnadTrace.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `web/src/components/IsnadTrace.tsx`**

```tsx
import type { QuotationOut } from "../api/client";
import { VERDICT_META, type Verdict } from "./VerdictBadge";

type ChainState = "complete" | "broken" | "terminated";

function chainState(verdict: Verdict): ChainState {
  if (verdict === "NOT_FOUND") return "terminated";
  return VERDICT_META[verdict].tone === "verified" ? "complete" : "broken";
}

function Link({
  id, label, children, broken = false, last = false,
}: {
  id: string; label: string; children: React.ReactNode; broken?: boolean; last?: boolean;
}) {
  return (
    <li
      data-testid={`link-${id}`}
      data-broken={String(broken)}
      style={{ display: "grid", gridTemplateColumns: "1.5rem 8rem 1fr", gap: "0.75rem",
               alignItems: "start", paddingBlock: "0.4rem", position: "relative" }}
    >
      {/* the ruled line and its ring — the mistara and the rosette */}
      <span aria-hidden="true" style={{ display: "block", position: "relative", height: "100%" }}>
        <span style={{
          position: "absolute", insetInlineStart: "0.5rem", insetBlockStart: "0.55rem",
          width: "0.5rem", height: "0.5rem", borderRadius: "50%",
          border: `1.5px solid ${broken ? "var(--rubric)" : "var(--ink-60)"}`,
          background: broken ? "var(--rubric)" : "transparent",
        }} />
        {!last && (
          <span style={{
            position: "absolute", insetInlineStart: "0.73rem", insetBlockStart: "1.1rem",
            bottom: "-0.4rem", width: 0,
            borderInlineStart: broken ? "1.5px dotted var(--rubric)" : "1.5px solid var(--ink-30)",
          }} />
        )}
      </span>
      <span className="data" style={{ paddingBlockStart: "0.15rem" }}>{label}</span>
      <span>{children}</span>
    </li>
  );
}

export function IsnadTrace({
  quotation, source,
}: {
  quotation: QuotationOut;
  source?: { license_id: string; title: string } | null;
}) {
  const verdict = quotation.verdict as Verdict;
  const state = chainState(verdict);
  const rec = quotation.record;
  const alsoCount = quotation.also_at?.length ?? 0;

  const textLinkBroken = verdict === "NEAR_MATCH" || verdict === "NOT_FOUND";
  const citationBroken = verdict === "WRONG_REFERENCE";

  return (
    <ol
      data-testid="chain"
      data-state={state}
      style={{ listStyle: "none", margin: 0, padding: 0, borderInlineStart: "none" }}
    >
      <Link id="quoted" label="you quoted">
        <span className="arabic" dir="rtl" lang="ar" style={{ fontSize: "var(--step-2)" }}>
          {quotation.quoted_text}
        </span>
      </Link>

      <Link id="normalized" label="normalized">
        <span className="data">
          {quotation.tier ? `tier: ${quotation.tier}` : "not normalized"}
          {quotation.score != null && ` · score ${quotation.score.toFixed(3)}`}
        </span>
      </Link>

      <Link id="matched" label="matched" broken={textLinkBroken}>
        {rec ? (
          <>
            <span>{rec.reference_display}</span>
            {alsoCount > 0 && (
              <span className="data" style={{ display: "block" }}>
                also appears at {alsoCount} other {alsoCount === 1 ? "place" : "places"}
              </span>
            )}
          </>
        ) : (
          <span style={{ color: "var(--ink-60)" }}>no match in this corpus</span>
        )}
      </Link>

      <Link id="cited" label="you cited" broken={citationBroken}>
        {quotation.given_reference ? (
          <span style={{ textDecoration: citationBroken ? "line-through" : "none" }}>
            {quotation.given_reference}
          </span>
        ) : (
          <span style={{ color: "var(--ink-60)" }}>no citation given</span>
        )}
      </Link>

      <Link id="source" label="source" last>
        {rec ? (
          <span className="data">
            {source?.title ?? "Tanzil Uthmani"} · {source?.license_id ?? "CC-BY-3.0"} · ⌗
            {rec.text_ar_sha256.slice(0, 8)}
          </span>
        ) : (
          <span className="data">—</span>
        )}
      </Link>
    </ol>
  );
}
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd web && npx vitest run tests/components/IsnadTrace.test.tsx`
Expected: PASS, 11 tests.

- [ ] **Step 5: Add the staggered resolve (spec §7)**

The chain should be seen being built rather than appearing whole. Links resolve
top to bottom, roughly 40 ms apart.

Add to `IsnadTrace.tsx`:

```tsx
import { motion, useReducedMotion } from "motion/react";
```

Change `Link` to accept an `index` prop and render as a motion element:

```tsx
function Link({
  id, label, children, broken = false, last = false, index = 0,
}: {
  id: string; label: string; children: React.ReactNode;
  broken?: boolean; last?: boolean; index?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.li
      data-testid={`link-${id}`}
      data-broken={String(broken)}
      initial={reduce ? false : { opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduce ? { duration: 0 } : { duration: 0.18, delay: index * 0.04 }}
      style={{ /* unchanged */ }}
    >
```

Pass `index={0..4}` to the five `Link` calls in order.

`useReducedMotion` is not decoration here: with motion disabled every link must
render immediately and in full. Motion draws attention to the verdict; it must
never be what communicates it.

- [ ] **Step 6: Prove the chain still renders with motion disabled**

Add to `web/tests/components/IsnadTrace.test.tsx`:

```tsx
it("renders every link when the user prefers reduced motion", () => {
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: q.includes("prefers-reduced-motion"),
    media: q, addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, onchange: null,
    dispatchEvent: () => false,
  }));
  render(<IsnadTrace quotation={base} />);
  expect(screen.getAllByTestId(/^link-/)).toHaveLength(5);
  expect(screen.getByTestId("chain")).toHaveAttribute("data-state", "complete");
});
```

Add `import { vi } from "vitest";` to the imports if not already present.

Run: `cd web && npx vitest run tests/components/IsnadTrace.test.tsx`
Expected: PASS, 12 tests.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/IsnadTrace.tsx web/tests/components/IsnadTrace.test.tsx
git commit -m "feat(web): the isnad trace

Five links in fixed order, and one rule: the chain either completes or it
visibly breaks, and you can see which link failed. A wrong reference
leaves the text link intact and strikes the citation; a near match breaks
at the text. Repeated verses disclose their other locations rather than
being silently attributed to one ayah."
```

---

### Task 6: `EvidenceCard` — verdict, trace, diff, and the caveat that must not be lost

**Files:**
- Create: `web/src/components/EvidenceCard.tsx`
- Test: `web/tests/components/EvidenceCard.test.tsx`

**Interfaces:**
- Consumes: `VerdictBadge`, `IsnadTrace`, `CharDiff`, `QuotationOut`.
- Produces: `EvidenceCard({ quotation, corpusScope }: { quotation: QuotationOut; corpusScope: string })`.

- [ ] **Step 1: Write the failing test**

Create `web/tests/components/EvidenceCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceCard } from "../../src/components/EvidenceCard";
import type { QuotationOut } from "../../src/api/client";

const SCOPE = "This corpus contains the Qur'an only. Absence of a quotation from this corpus does not establish that it is fabricated.";

const base = {
  quoted_text: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", start: 0, end: 20,
  verdict: "EXACT", tier: "light", score: 1,
  record: { id: "quran:112:1", reference_display: "Al-Ikhlas 112:1",
            text_ar: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", text_ar_sha256: "abc12345",
            surah: 112, ayah: 1, translation_en: "Say: He is Allah, the One!",
            translation_disclaimer: "No translation of Quran can be a hundred percent accurate." },
  given_reference: null, diff: null, also_at: [],
} as unknown as QuotationOut;

const q = (over: Partial<QuotationOut>) => ({ ...base, ...over }) as QuotationOut;

describe("EvidenceCard", () => {
  it("attaches the corpus-scope caveat to a NOT_FOUND verdict", () => {
    render(<EvidenceCard quotation={q({ verdict: "NOT_FOUND", record: null })} corpusScope={SCOPE} />);
    expect(screen.getByTestId("scope-caveat")).toHaveTextContent(/does not establish that it is fabricated/i);
  });

  it("does not attach the caveat to a verified verdict", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    expect(screen.queryByTestId("scope-caveat")).toBeNull();
  });

  it("renders the diff when there is one", () => {
    render(<EvidenceCard quotation={q({ verdict: "NEAR_MATCH", diff: [["quoted-only", "x"], ["corpus-only", "y"]] })} corpusScope={SCOPE} />);
    expect(screen.getByTestId("diff")).toBeInTheDocument();
  });

  it("shows the English translation with its accuracy disclaimer", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    expect(screen.getByText(/Say: He is Allah, the One!/)).toBeInTheDocument();
    expect(screen.getByText(/hundred percent accurate/i)).toBeInTheDocument();
  });

  it("never shows a translation without its disclaimer", () => {
    render(<EvidenceCard quotation={base} corpusScope={SCOPE} />);
    const translation = screen.queryByTestId("translation");
    const disclaimer = screen.queryByTestId("translation-disclaimer");
    expect(Boolean(translation)).toBe(Boolean(disclaimer));
  });

  it("renders the verdict label", () => {
    render(<EvidenceCard quotation={q({ verdict: "WRONG_REFERENCE", given_reference: "2:255" })} corpusScope={SCOPE} />);
    expect(screen.getByText(/wrong reference/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd web && npx vitest run tests/components/EvidenceCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `web/src/components/EvidenceCard.tsx`**

```tsx
import type { QuotationOut } from "../api/client";
import { CharDiff, type DiffOp } from "./CharDiff";
import { IsnadTrace } from "./IsnadTrace";
import { VerdictBadge, type Verdict } from "./VerdictBadge";

export function EvidenceCard({
  quotation, corpusScope,
}: {
  quotation: QuotationOut;
  corpusScope: string;
}) {
  const verdict = quotation.verdict as Verdict;
  const rec = quotation.record;

  return (
    <article
      style={{
        border: "var(--rule)",
        borderInlineStart: `3px solid ${verdict === "NOT_FOUND" ? "var(--ink-30)" : "var(--ink-12)"}`,
        padding: "1rem 1.25rem",
        marginBlockEnd: "1rem",
        background: "color-mix(in srgb, var(--page) 94%, white)",
      }}
    >
      <header style={{ marginBlockEnd: "0.75rem" }}>
        <VerdictBadge verdict={verdict} />
      </header>

      <IsnadTrace quotation={quotation} />

      <CharDiff diff={(quotation.diff as DiffOp[] | null) ?? null} />

      {rec?.translation_en && (
        <div style={{ marginBlockStart: "0.9rem", paddingBlockStart: "0.6rem", borderBlockStart: "var(--rule)" }}>
          <p data-testid="translation" style={{ margin: 0 }}>{rec.translation_en}</p>
          <p data-testid="translation-disclaimer" className="data" style={{ margin: "0.3rem 0 0" }}>
            {rec.translation_disclaimer}
          </p>
        </div>
      )}

      {verdict === "NOT_FOUND" && (
        <p
          data-testid="scope-caveat"
          className="data"
          style={{ marginBlockStart: "0.9rem", paddingBlockStart: "0.6rem",
                   borderBlockStart: "var(--rule)", color: "var(--ink)" }}
        >
          {corpusScope}
        </p>
      )}
    </article>
  );
}
```

The caveat renders only on `NOT_FOUND` because that is the only verdict a reader could mistake for an accusation of fabrication.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd web && npx vitest run tests/components/EvidenceCard.test.tsx`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/EvidenceCard.tsx web/tests/components/EvidenceCard.test.tsx
git commit -m "feat(web): evidence card with the corpus-scope caveat bound to NOT_FOUND

The caveat is attached to the verdict, not parked in a page footer, and a
test pins it. NOT_FOUND is the one verdict a reader could mistake for an
accusation, and this corpus holds no Hadith at all."
```

---

### Task 7: `MarkedText` — the user's text, marked and never rewritten

**Files:**
- Create: `web/src/components/MarkedText.tsx`
- Test: `web/tests/components/MarkedText.test.tsx`

**Interfaces:**
- Consumes: `QuotationOut` (`start`, `end`, `verdict`).
- Produces: `MarkedText({ text, quotations }: { text: string; quotations: QuotationOut[] })`.

- [ ] **Step 1: Write the failing test**

Create `web/tests/components/MarkedText.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkedText } from "../../src/components/MarkedText";
import type { QuotationOut } from "../../src/api/client";

const span = (start: number, end: number, verdict: string) =>
  ({ start, end, verdict, quoted_text: "", tier: null, score: 0,
     record: null, given_reference: null, diff: null, also_at: [] }) as unknown as QuotationOut;

describe("MarkedText", () => {
  it("reproduces the user's text exactly", () => {
    const text = "He said «قل هو الله احد» yesterday.";
    render(<MarkedText text={text} quotations={[span(8, 24, "EXACT")]} />);
    expect(screen.getByTestId("marked").textContent).toBe(text);
  });

  it("never substitutes the corpus reading for what the user typed", () => {
    const typo = "قل هو الله احدق";
    render(<MarkedText text={typo} quotations={[span(0, typo.length, "NEAR_MATCH")]} />);
    expect(screen.getByTestId("marked").textContent).toBe(typo);
    expect(screen.getByTestId("marked").textContent).not.toContain("احد ");
  });

  it("marks each span with its verdict", () => {
    render(<MarkedText text="aaaabbbb" quotations={[span(0, 4, "EXACT"), span(4, 8, "NOT_FOUND")]} />);
    expect(screen.getByTestId("span-0")).toHaveAttribute("data-verdict", "EXACT");
    expect(screen.getByTestId("span-1")).toHaveAttribute("data-verdict", "NOT_FOUND");
  });

  it("renders plain text unchanged when there are no spans", () => {
    render(<MarkedText text="nothing to mark here" quotations={[]} />);
    expect(screen.getByTestId("marked").textContent).toBe("nothing to mark here");
  });

  it("handles spans given out of order without corrupting the text", () => {
    const text = "aaaabbbbcccc";
    render(<MarkedText text={text} quotations={[span(8, 12, "EXACT"), span(0, 4, "NOT_FOUND")]} />);
    expect(screen.getByTestId("marked").textContent).toBe(text);
  });

  it("gives each mark an accessible description of its verdict", () => {
    render(<MarkedText text="aaaa" quotations={[span(0, 4, "WRONG_REFERENCE")]} />);
    expect(screen.getByTestId("span-0")).toHaveAttribute("title", expect.stringMatching(/wrong reference/i));
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd web && npx vitest run tests/components/MarkedText.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `web/src/components/MarkedText.tsx`**

```tsx
import type { QuotationOut } from "../api/client";
import { VERDICT_META, type Verdict } from "./VerdictBadge";

const UNDERLINE: Record<Verdict, string> = {
  EXACT:             "2px solid var(--verdigris)",
  EXACT_ORTHOGRAPHY: "2px dashed var(--verdigris)",
  NEAR_MATCH:        "2px wavy var(--rubric)",
  WRONG_REFERENCE:   "2px dotted var(--rubric)",
  NOT_FOUND:         "2px solid var(--ink-30)",
};

/**
 * The user's text with each span marked in place.
 *
 * The text is never rewritten. Sanad's non-goals forbid silently correcting a
 * quotation, and this component is where that promise is kept: it renders the
 * exact input string, adding marks around ranges and nothing else.
 */
export function MarkedText({
  text, quotations,
}: {
  text: string;
  quotations: QuotationOut[];
}) {
  const spans = [...quotations].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  spans.forEach((s, i) => {
    if (s.start > cursor) parts.push(<span key={`t${i}`}>{text.slice(cursor, s.start)}</span>);
    const verdict = s.verdict as Verdict;
    parts.push(
      <mark
        key={`s${i}`}
        data-testid={`span-${i}`}
        data-verdict={verdict}
        title={VERDICT_META[verdict].label}
        style={{
          background: "transparent",
          color: "inherit",
          textDecoration: `underline ${UNDERLINE[verdict]}`,
          textUnderlineOffset: "0.3em",
          textDecorationSkipInk: "none",
        }}
      >
        {text.slice(s.start, s.end)}
      </mark>
    );
    cursor = Math.max(cursor, s.end);
  });

  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);

  return (
    <p
      data-testid="marked"
      style={{ maxWidth: "var(--measure)", whiteSpace: "pre-wrap", margin: 0, lineHeight: 1.9 }}
    >
      {parts}
    </p>
  );
}
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd web && npx vitest run tests/components/MarkedText.test.tsx`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/MarkedText.tsx web/tests/components/MarkedText.test.tsx
git commit -m "feat(web): mark the user's text in place, never rewriting it

A test pins that the rendered text is byte-identical to the input even
when a span is a misquote. Silently correcting a quotation is an explicit
non-goal, and this is where that promise is kept."
```

---

### Task 8: `HandoffCard`, `ClaimList`, and `ErrorState`

Three small display components, batched because each is a handful of lines and they share one review surface.

**Files:**
- Create: `web/src/components/HandoffCard.tsx`, `web/src/components/ClaimList.tsx`, `web/src/components/ErrorState.tsx`
- Test: `web/tests/components/HandoffCard.test.tsx`, `web/tests/components/ClaimList.test.tsx`, `web/tests/components/ErrorState.test.tsx`

**Interfaces:**
- Produces:
  - `HandoffCard({ risk }: { risk: string })`
  - `ClaimList({ claims }: { claims: ClaimOut[] })`
  - `ErrorState({ kind, detail }: { kind: "unreachable" | "server" | "no-arabic" | "idle"; detail?: string })`

- [ ] **Step 1: Write the failing tests**

`web/tests/components/HandoffCard.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HandoffCard } from "../../src/components/HandoffCard";

describe("HandoffCard", () => {
  it("says a person should answer, for a personal ruling", () => {
    render(<HandoffCard risk="PERSONAL_RULING" />);
    expect(screen.getByRole("alert")).toHaveTextContent(/qualified/i);
  });

  it("does not render any verdict", () => {
    render(<HandoffCard risk="PERSONAL_RULING" />);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("uses different wording for a high-risk topic", () => {
    render(<HandoffCard risk="HIGH_RISK" />);
    expect(screen.getByRole("alert").textContent).toMatch(/sensitive/i);
  });
});
```

`web/tests/components/ClaimList.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClaimList } from "../../src/components/ClaimList";

describe("ClaimList", () => {
  it("renders nothing when there are no claims", () => {
    const { container } = render(<ClaimList claims={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows each claim's label and note", () => {
    render(<ClaimList claims={[{ kind: "unanimity", label: "Unanimity claimed", note: "Requires named evidence." }]} />);
    expect(screen.getByText("Unanimity claimed")).toBeInTheDocument();
    expect(screen.getByText(/requires named evidence/i)).toBeInTheDocument();
  });
});
```

`web/tests/components/ErrorState.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorState } from "../../src/components/ErrorState";

describe("ErrorState", () => {
  it("says the verifier cannot be reached, rather than showing nothing", () => {
    render(<ErrorState kind="unreachable" />);
    expect(screen.getByRole("alert")).toHaveTextContent(/cannot reach the verifier/i);
  });

  it("distinguishes 'nothing to check' from 'checked and not found'", () => {
    render(<ErrorState kind="no-arabic" />);
    const text = screen.getByRole("status").textContent ?? "";
    expect(text).toMatch(/no quotations found to check/i);
    expect(text).not.toMatch(/not in this corpus/i);
  });

  it("reports a server error with its status", () => {
    render(<ErrorState kind="server" detail="503" />);
    expect(screen.getByRole("alert")).toHaveTextContent("503");
  });

  it("invites action when idle", () => {
    render(<ErrorState kind="idle" />);
    expect(screen.getByRole("status")).toHaveTextContent(/paste/i);
  });
});
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `cd web && npx vitest run tests/components/HandoffCard.test.tsx tests/components/ClaimList.test.tsx tests/components/ErrorState.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement `web/src/components/HandoffCard.tsx`**

```tsx
const COPY: Record<string, { heading: string; body: string }> = {
  PERSONAL_RULING: {
    heading: "This needs a qualified person, not software",
    body: "You are asking about your own situation. Sanad checks whether a quotation is genuine; it cannot weigh your circumstances, and it will not try. Take this to a qualified scholar who can ask you the questions that matter.",
  },
  HIGH_RISK: {
    heading: "This topic is too sensitive for an automated answer",
    body: "Sanad verifies quotations. It does not rule on sensitive questions, and an answer assembled from matched text would carry an authority it has not earned.",
  },
};

export function HandoffCard({ risk }: { risk: string }) {
  const copy = COPY[risk] ?? COPY.PERSONAL_RULING;
  return (
    <div
      role="alert"
      style={{ border: `1px solid var(--rubric)`, borderInlineStart: "3px solid var(--rubric)",
               padding: "1.25rem 1.5rem", maxWidth: "var(--measure)" }}
    >
      <h2 style={{ margin: "0 0 0.5rem", fontSize: "var(--step-1)", color: "var(--rubric)" }}>
        {copy.heading}
      </h2>
      <p style={{ margin: 0 }}>{copy.body}</p>
    </div>
  );
}
```

- [ ] **Step 4: Implement `web/src/components/ClaimList.tsx`**

```tsx
import type { ClaimOut } from "../api/client";

export function ClaimList({ claims }: { claims: ClaimOut[] }) {
  if (claims.length === 0) return null;
  return (
    <section style={{ marginBlockStart: "1.5rem" }}>
      <h2 className="data" style={{ margin: "0 0 0.5rem" }}>claims that a quotation cannot support</h2>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {claims.map((c) => (
          <li key={c.kind} style={{ borderBlockStart: "var(--rule)", paddingBlock: "0.6rem", maxWidth: "var(--measure)" }}>
            <strong style={{ display: "block" }}>{c.label}</strong>
            <span style={{ color: "var(--ink-60)" }}>{c.note}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 5: Implement `web/src/components/ErrorState.tsx`**

```tsx
const MESSAGES = {
  unreachable: {
    role: "alert" as const,
    text: "Cannot reach the verifier. The service may be starting up — try again in a moment.",
  },
  server: {
    role: "alert" as const,
    text: "The verifier returned an error.",
  },
  "no-arabic": {
    role: "status" as const,
    text: "No quotations found to check. Sanad looks for Arabic text and quoted passages.",
  },
  idle: {
    role: "status" as const,
    text: "Paste text above to check its quotations.",
  },
};

/**
 * "We found nothing to check" and "we checked and it is not in the corpus" are
 * different statements and must never collapse into one another. Silence must
 * never be mistakable for a verdict.
 */
export function ErrorState({
  kind, detail,
}: {
  kind: keyof typeof MESSAGES;
  detail?: string;
}) {
  const m = MESSAGES[kind];
  return (
    <p role={m.role} style={{ color: "var(--ink-60)", maxWidth: "var(--measure)" }}>
      {m.text}
      {detail && <span className="data"> ({detail})</span>}
    </p>
  );
}
```

- [ ] **Step 6: Run tests, confirm they pass**

Run: `cd web && npx vitest run tests/components`
Expected: PASS — all component suites green.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/HandoffCard.tsx web/src/components/ClaimList.tsx web/src/components/ErrorState.tsx web/tests/components
git commit -m "feat(web): handoff, claims, and error states

A handoff card renders no verdict at all — the warning instead of a
verdict, not alongside one. Error states keep 'nothing to check' and
'checked and not found' as distinct statements, because silence must
never be mistakable for a verdict."
```

---

### Task 9: `useVerify` and the Verify screen

**Files:**
- Create: `web/src/api/useVerify.ts`, `web/src/screens/Verify.tsx`
- Modify: `web/src/App.tsx`
- Test: `web/tests/screens/Verify.test.tsx`

**Interfaces:**
- Consumes: everything above.
- Produces: `useVerify()` returning `{ state, result, error, run(text: string), reset() }` where `state` is `"idle" | "loading" | "ok" | "unreachable" | "error"`.

- [ ] **Step 1: Write the failing test**

Create `web/tests/screens/Verify.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, afterEach } from "vitest";
import { Verify } from "../../src/screens/Verify";

const SCOPE = "This corpus contains the Qur'an only. Absence of a quotation from this corpus does not establish that it is fabricated.";

function reply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

const verified = {
  quotations: [{
    quoted_text: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", start: 0, end: 20, verdict: "EXACT",
    tier: "light", score: 1,
    record: { id: "quran:112:1", reference_display: "Al-Ikhlas 112:1",
              text_ar: "قُلْ هُوَ ٱللَّهُ أَحَدٌ", text_ar_sha256: "abc12345", surah: 112, ayah: 1,
              translation_en: "Say: He is Allah, the One!", translation_disclaimer: "Not a replacement." },
    given_reference: null, diff: null, also_at: [] }],
  claims: [], risk: "GENERAL", requires_handoff: false, overall: "grounded", corpus_scope: SCOPE,
};

afterEach(() => vi.unstubAllGlobals());

describe("Verify screen", () => {
  it("shows a verdict after verifying", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(verified)));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "قُلْ هُوَ ٱللَّهُ أَحَدٌ");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByText(/^Verified$/)).toBeInTheDocument());
  });

  it("replaces the evidence stack with a handoff card on a personal ruling", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...verified, risk: "PERSONAL_RULING", requires_handoff: true, overall: "handoff",
    })));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "Can I marry my cousin?");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/qualified/i));
    // the critical assertion: no verdict is shown at all
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("says the verifier is unreachable rather than rendering an empty result", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "anything");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/cannot reach the verifier/i));
  });

  it("distinguishes no-quotations-found from not-in-corpus", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...verified, quotations: [], overall: "insufficient_span",
    })));
    const user = userEvent.setup();
    render(<Verify />);
    await user.type(screen.getByRole("textbox"), "plain english");
    await user.click(screen.getByRole("button", { name: /verify/i }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/no quotations found to check/i));
    expect(screen.queryByText(/not in this corpus/i)).toBeNull();
  });

  it("disables verify while the input is empty", () => {
    render(<Verify />);
    expect(screen.getByRole("button", { name: /verify/i })).toBeDisabled();
  });

  it("loads an example that exercises several verdicts", async () => {
    const user = userEvent.setup();
    render(<Verify />);
    await user.click(screen.getByRole("button", { name: /example/i }));
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value.length).toBeGreaterThan(40);
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd web && npx vitest run tests/screens/Verify.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `web/src/api/useVerify.ts`**

```ts
import { useCallback, useState } from "react";
import { ApiError, ApiUnreachable, verify, type VerifyResponse } from "./client";

export type VerifyState = "idle" | "loading" | "ok" | "unreachable" | "error";

export function useVerify() {
  const [state, setState] = useState<VerifyState>("idle");
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | undefined>();

  const run = useCallback(async (text: string) => {
    setState("loading");
    setError(undefined);
    try {
      setResult(await verify(text));
      setState("ok");
    } catch (e) {
      setResult(null);
      if (e instanceof ApiUnreachable) setState("unreachable");
      else if (e instanceof ApiError) { setState("error"); setError(String(e.status)); }
      else { setState("error"); setError("unexpected"); }
    }
  }, []);

  const reset = useCallback(() => {
    setState("idle"); setResult(null); setError(undefined);
  }, []);

  return { state, result, error, run, reset };
}
```

- [ ] **Step 4: Implement `web/src/screens/Verify.tsx`**

```tsx
import { useState } from "react";
import { useVerify } from "../api/useVerify";
import { ClaimList } from "../components/ClaimList";
import { ErrorState } from "../components/ErrorState";
import { EvidenceCard } from "../components/EvidenceCard";
import { HandoffCard } from "../components/HandoffCard";
import { MarkedText } from "../components/MarkedText";

const EXAMPLE =
  "Islam teaches tawhid. The Qur'an says «قُلْ هُوَ " +
  "ٱللَّهُ أَحَدٌ» " +
  "(Al-Baqarah 2:255). All scholars agree that this settles the matter.";

export function Verify() {
  const [text, setText] = useState("");
  const { state, result, error, run } = useVerify();

  return (
    <main style={{ maxWidth: "72rem", margin: "0 auto", padding: "2rem 1.5rem 6rem" }}>
      <header style={{ marginBlockEnd: "2rem" }}>
        <h1 style={{ fontSize: "var(--step-3)", margin: "0 0 0.25rem", fontWeight: 600 }}>Sanad</h1>
        <p className="data" style={{ margin: 0 }}>
          check whether a quotation is genuinely in the Qur'an, and see the chain back to its source
        </p>
      </header>

      <form
        onSubmit={(e) => { e.preventDefault(); run(text); }}
        style={{ marginBlockEnd: "2rem" }}
      >
        <label htmlFor="input" className="data" style={{ display: "block", marginBlockEnd: "0.4rem" }}>
          paste anything — a chatbot answer, a sermon, a forum post
        </label>
        <textarea
          id="input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          style={{
            width: "100%", padding: "0.9rem 1rem", background: "color-mix(in srgb, var(--page) 94%, white)",
            border: "var(--rule)", color: "var(--ink)", font: "inherit", lineHeight: 1.7, resize: "vertical",
          }}
        />
        <div style={{ display: "flex", gap: "0.75rem", marginBlockStart: "0.75rem" }}>
          <button type="submit" disabled={text.trim().length === 0 || state === "loading"}
                  style={{ font: "inherit", padding: "0.5rem 1.25rem", border: "1px solid var(--ink)",
                           background: "var(--ink)", color: "var(--page)", cursor: "pointer" }}>
            {state === "loading" ? "Checking…" : "Verify"}
          </button>
          <button type="button" onClick={() => setText(EXAMPLE)}
                  style={{ font: "inherit", padding: "0.5rem 1.25rem", border: "1px solid var(--ink-30)",
                           background: "transparent", color: "var(--ink)", cursor: "pointer" }}>
            Load example
          </button>
        </div>
      </form>

      {state === "idle" && <ErrorState kind="idle" />}
      {state === "unreachable" && <ErrorState kind="unreachable" />}
      {state === "error" && <ErrorState kind="server" detail={error} />}

      {state === "ok" && result && (
        <>
          <section style={{ marginBlockEnd: "2rem" }}>
            <h2 className="data" style={{ margin: "0 0 0.6rem" }}>your text</h2>
            <MarkedText text={text} quotations={result.quotations} />
          </section>

          {result.requires_handoff ? (
            <HandoffCard risk={result.risk} />
          ) : result.quotations.length === 0 ? (
            <ErrorState kind="no-arabic" />
          ) : (
            <section>
              <h2 className="data" style={{ margin: "0 0 0.6rem" }}>evidence</h2>
              {result.quotations.map((q, i) => (
                <EvidenceCard key={i} quotation={q} corpusScope={result.corpus_scope} />
              ))}
            </section>
          )}

          {!result.requires_handoff && <ClaimList claims={result.claims} />}
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 5: Wire `App.tsx`**

```tsx
import { Verify } from "./screens/Verify";

export default function App() {
  return <Verify />;
}
```

- [ ] **Step 6: Run tests, confirm they pass**

Run: `cd web && npx vitest run`
Expected: PASS — all suites.

- [ ] **Step 7: See it running against the real API**

```bash
SANAD_AUDIT_DB=/tmp/sanad-audit.db \
  .venv/bin/uvicorn sanad.api.app:create_app --factory --port 8000 &
cd web && npm run dev
```

Open the printed URL, click **Load example**, then **Verify**. You should see `WRONG_REFERENCE` on the quotation and a unanimity claim listed. Report what you actually saw.

- [ ] **Step 8: Commit**

```bash
git add web/src/api/useVerify.ts web/src/screens/Verify.tsx web/src/App.tsx web/tests/screens
git commit -m "feat(web): the verify screen

A personal-ruling result replaces the evidence stack entirely — the
handoff card instead of a verdict, and a test asserts no verdict renders
at all. An unreachable API says so rather than rendering an empty stack,
and 'no quotations found' stays distinct from 'not in this corpus'."
```

---

### Task 10: `ProvenancePanel`

**Files:**
- Create: `web/src/components/ProvenancePanel.tsx`
- Modify: `web/src/App.tsx`, `web/src/screens/Verify.tsx`
- Test: `web/tests/components/ProvenancePanel.test.tsx`

**Interfaces:**
- Consumes: `getCorpus()`, `CorpusResponse`.
- Produces: `ProvenancePanel({ onClose }: { onClose: () => void })`.

- [ ] **Step 1: Write the failing test**

Create `web/tests/components/ProvenancePanel.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { ProvenancePanel } from "../../src/components/ProvenancePanel";

const NOTICE = "# PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK\n#  Tanzil Quran Text (Uthmani, Version 1.1)\n#  License: Creative Commons Attribution 3.0";

const corpus = {
  db_sha256: "8774f3883d2547401c423e682f148af3012623872b33797b27207a141b3b2d79",
  db_path: "data/sanad-quran.db",
  stats: { records: 6236, sources: 2, translations: 6236 },
  scope: "This corpus contains the Qur'an only.",
  sources: [
    { id: "tanzil-uthmani-1.1", kind: "quran-arabic", title: "Tanzil Qur'an Text (Uthmani)",
      publisher: "Tanzil Project", edition: "1.1", url: "https://tanzil.net/",
      license_id: "CC-BY-3.0", license_url: "https://tanzil.net/docs/text_license",
      attribution: NOTICE, retrieved_at: "2026-09-20", upstream_sha256: "36da55e2", modifications: "none" },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("ProvenancePanel", () => {
  it("shows the corpus checksum", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(corpus), { status: 200 })));
    render(<ProvenancePanel onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText(/8774f388/)).toBeInTheDocument());
  });

  it("reproduces the licence notice verbatim, not summarised", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(corpus), { status: 200 })));
    render(<ProvenancePanel onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByTestId("attribution-tanzil-uthmani-1.1").textContent).toBe(NOTICE);
    });
  });

  it("shows the record count", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(corpus), { status: 200 })));
    render(<ProvenancePanel onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText(/6,?236/)).toBeInTheDocument());
  });

  it("says the verifier is unreachable when the corpus cannot be fetched", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));
    render(<ProvenancePanel onClose={() => {}} />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/cannot reach the verifier/i));
  });
});
```

The second test asserts exact equality, not `toContain`. Tanzil's block says "DO NOT REMOVE OR CHANGE", and Stage A went to some trouble to store it byte-verbatim; the UI must not undo that.

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd web && npx vitest run tests/components/ProvenancePanel.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `web/src/components/ProvenancePanel.tsx`**

```tsx
import { useEffect, useState } from "react";
import { ApiUnreachable, getCorpus, type CorpusResponse } from "../api/client";
import { ErrorState } from "./ErrorState";

export function ProvenancePanel({ onClose }: { onClose: () => void }) {
  const [corpus, setCorpus] = useState<CorpusResponse | null>(null);
  const [failed, setFailed] = useState<"unreachable" | "server" | null>(null);

  useEffect(() => {
    getCorpus()
      .then(setCorpus)
      .catch((e) => setFailed(e instanceof ApiUnreachable ? "unreachable" : "server"));
  }, []);

  if (failed) return <ErrorState kind={failed} />;
  if (!corpus) return <p className="data">Loading the corpus manifest…</p>;

  return (
    <section style={{ maxWidth: "var(--measure)" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 style={{ fontSize: "var(--step-2)", margin: "0 0 0.5rem" }}>What this corpus is</h2>
        <button onClick={onClose} className="data"
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--ink)" }}>
          close
        </button>
      </header>

      <p>{corpus.scope}</p>

      <dl className="data" style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "0.3rem 1rem", margin: "1rem 0" }}>
        <dt>records</dt><dd style={{ margin: 0 }}>{corpus.stats.records.toLocaleString()}</dd>
        <dt>translations</dt><dd style={{ margin: 0 }}>{corpus.stats.translations.toLocaleString()}</dd>
        <dt>database</dt><dd style={{ margin: 0, wordBreak: "break-all" }}>⌗{corpus.db_sha256}</dd>
      </dl>

      {corpus.sources.map((s) => (
        <article key={s.id} style={{ borderBlockStart: "var(--rule)", paddingBlock: "1rem" }}>
          <h3 style={{ fontSize: "var(--step-1)", margin: "0 0 0.2rem" }}>{s.title}</h3>
          <p className="data" style={{ margin: "0 0 0.6rem" }}>
            {s.license_id}
            {s.license_url && <> · <a href={s.license_url} style={{ color: "inherit" }}>licence</a></>}
            {" · "}retrieved {s.retrieved_at} · modifications: {s.modifications}
          </p>
          {/* Verbatim. Tanzil's notice says it must not be changed, and Stage A
              stores it byte-for-byte; rendering it any other way would undo that. */}
          <pre
            data-testid={`attribution-${s.id}`}
            className="data"
            style={{ whiteSpace: "pre-wrap", margin: 0, padding: "0.75rem",
                     background: "color-mix(in srgb, var(--page) 90%, var(--ink))",
                     border: "var(--rule)", overflowX: "auto" }}
          >{s.attribution}</pre>
        </article>
      ))}
    </section>
  );
}
```

- [ ] **Step 4: Add a link to it from the Verify screen**

In `web/src/App.tsx`, hold the open/closed state:

```tsx
import { useState } from "react";
import { ProvenancePanel } from "./components/ProvenancePanel";
import { Verify } from "./screens/Verify";

export default function App() {
  const [showProvenance, setShowProvenance] = useState(false);
  return (
    <>
      <Verify />
      <div style={{ maxWidth: "72rem", margin: "0 auto", padding: "0 1.5rem 4rem" }}>
        {showProvenance ? (
          <ProvenancePanel onClose={() => setShowProvenance(false)} />
        ) : (
          <button onClick={() => setShowProvenance(true)} className="data"
                  style={{ background: "none", border: "none", padding: 0, cursor: "pointer",
                           color: "var(--ink)", textDecoration: "underline" }}>
            what this corpus is, and where it came from
          </button>
        )}
      </div>
    </>
  );
}
```

- [ ] **Step 5: Run tests, confirm they pass**

Run: `cd web && npx vitest run`
Expected: PASS — all suites.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/ProvenancePanel.tsx web/src/App.tsx web/tests/components/ProvenancePanel.test.tsx
git commit -m "feat(web): provenance panel

Renders the corpus manifest: sources, licences, record counts and the
database checksum. The Tanzil notice is reproduced verbatim and a test
asserts exact equality — the notice says it must not be changed, and
Stage A stores it byte-for-byte."
```

---

### Task 11: Vercel deployment

**Files:**
- Create: `app.py` (repo root), `vercel.json` (repo root)
- Modify: `.gitignore`, `README.md`, `index.html`
- Test: `tests/api/test_vercel_entrypoint.py`

**Interfaces:**
- Produces: a root-level `app` ASGI application that Vercel's Python runtime loads.

- [ ] **Step 1: Write the failing test**

Create `tests/api/test_vercel_entrypoint.py`:

```python
def test_root_entrypoint_exposes_an_asgi_app():
    """Vercel's Python runtime loads a top-level `app` from app.py."""
    import app as entrypoint
    assert hasattr(entrypoint, "app")
    from fastapi import FastAPI
    assert isinstance(entrypoint.app, FastAPI)


def test_root_entrypoint_serves_health(monkeypatch, tmp_path):
    monkeypatch.setenv("SANAD_AUDIT_DB", str(tmp_path / "audit.db"))
    from fastapi.testclient import TestClient
    import importlib
    import app as entrypoint
    importlib.reload(entrypoint)
    body = TestClient(entrypoint.app).get("/api/health").json()
    assert body["records"] == 6236
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `.venv/bin/python -m pytest tests/api/test_vercel_entrypoint.py -v`
Expected: FAIL — no module named `app`.

- [ ] **Step 3: Create the root `app.py`**

```python
"""Vercel entrypoint.

Vercel's Python runtime loads a top-level `app` from app.py at the project
root. Sanad's application lives behind a factory in api/sanad/api/app.py, so
this module is a shim and nothing more — no logic belongs here.

The audit log must point at /tmp: serverless filesystems are read-only
everywhere else. The corpus is already opened read-only, so it is unaffected.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "api"))

os.environ.setdefault("SANAD_AUDIT_DB", "/tmp/sanad-audit.db")

from sanad.api.app import create_app  # noqa: E402

app = create_app()
```

- [ ] **Step 4: Create `vercel.json`**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "buildCommand": "cd web && npm ci && npm run build",
  "outputDirectory": "web/dist",
  "functions": {
    "app.py": {
      "excludeFiles": "{tests/**,eval/**,docs/**,web/node_modules/**,web/src/**,web/tests/**,.venv/**,.superpowers/**,.github/**,**/__pycache__/**,**/*.pyc,*.egg-info/**}"
    }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/app.py" }
  ]
}
```

`excludeFiles` matters: Vercel bundles everything reachable with no tree-shaking, so without this the function would carry the test suite, the eval corpus and the docs. `data/sanad-quran.db` is deliberately not excluded — the corpus is the point.

- [ ] **Step 5: Run tests, confirm they pass**

Run: `.venv/bin/python -m pytest tests/api/test_vercel_entrypoint.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 6: Run the full Python suite and the web suite**

Run: `.venv/bin/python -m pytest -q` then `cd web && npx vitest run`
Expected: both green. `git status` clean.

- [ ] **Step 7: Update `.gitignore`**

Add:
```
web/node_modules/
web/dist/
.vercel/
```

- [ ] **Step 8: Update `README.md`**

Add a section after "Run locally":

```markdown
## The live demo

The verification engine runs at the Vercel deployment; GitHub Pages serves the
Phase 0 prototype only, because Pages cannot run Python.

Run the full stack locally:

```bash
SANAD_AUDIT_DB=/tmp/sanad-audit.db \
  uvicorn sanad.api.app:create_app --factory --port 8000 &
cd web && npm install && npm run dev
```

The API's interactive documentation is at `http://localhost:8000/docs`.
```

- [ ] **Step 9: Leave the Pages banner alone for now**

The banner currently points at the Docker command, which is accurate. It should
also name the live Vercel URL — but that URL does not exist until the first
deploy succeeds, and inventing one would put a dead link in the honesty section
of a tool about honesty. This is a post-deploy follow-up, recorded here so it
is not forgotten: once Vercel reports the production URL, update the banner in
`index.html` and the "Live demo" line in `README.md` in one commit.

- [ ] **Step 10: Commit**

```bash
git add app.py vercel.json .gitignore README.md index.html tests/api/test_vercel_entrypoint.py
git commit -m "feat: deploy the frontend and API as one Vercel project

Same origin, so no CORS and no second deploy to keep in sync. The audit
log points at /tmp because serverless filesystems are read-only
elsewhere; the corpus is already opened read-only and is unaffected.

excludeFiles is load-bearing: Vercel bundles everything reachable with no
tree-shaking, so without it the function would ship the test suite, the
eval cases and the docs."
```

---

## Definition of Done

- [ ] `cd web && npx vitest run` green
- [ ] `cd web && npm run lint:types` clean
- [ ] `cd web && npm run build` succeeds
- [ ] `.venv/bin/python -m pytest -q` still green (254 before this plan)
- [ ] `git status` clean after a full run of both suites
- [ ] The dev server renders a verdict against the real API
- [ ] A personal-ruling question renders the handoff card and **no** verdict
- [ ] An unreachable API renders "cannot reach the verifier", not an empty stack
- [ ] The Tanzil notice renders byte-identical in the provenance panel
- [ ] CI fails if `web/src/api/types.ts` drifts from `/openapi.json`

## Deliberately not in this plan

**No Ask mode**, no stub, no static pipeline diagram. Stage B builds it.

**No search UI.** `GET /api/search` stays available to API consumers; nothing in
the frontend calls it. Cut during brainstorming — nobody asked for it, and a
search box competes with the paste-and-dissect flow that is the demo.

**No verification logic anywhere in `web/`.** Every verdict is read from the
API response. This is the constraint most worth enforcing at review: a second
verifier that can disagree with the first is the defect Stage A spent its time
hunting.
