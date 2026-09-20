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
        <dt>records</dt><dd data-testid="stat-records" style={{ margin: 0 }}>{corpus.stats.records.toLocaleString()}</dd>
        <dt>translations</dt><dd data-testid="stat-translations" style={{ margin: 0 }}>{corpus.stats.translations.toLocaleString()}</dd>
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

          {/* Where to go to check this yourself, and exactly what number to
              expect when you do. upstream_sha256 is deliberately NOT a hash of
              the downloaded file — see the note below — so mislabelling it would
              send a sceptic to sha256sum, get a different number, and reasonably
              conclude we lied. */}
          <dl className="data" style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "0.3rem 1rem", margin: "0 0 0.75rem" }}>
            <dt>source</dt>
            <dd data-testid={`source-url-${s.id}`} style={{ margin: 0, wordBreak: "break-all" }}>
              <a href={s.url} style={{ color: "inherit" }}>{s.url}</a>
            </dd>
            <dt>content sha256</dt>
            <dd data-testid={`upstream-sha256-${s.id}`} style={{ margin: 0, wordBreak: "break-all" }}>
              ⌗{s.upstream_sha256}
              <span style={{ display: "block", color: "var(--ink-60)" }}>
                of the verse payload only — the "surah|ayah|text" lines joined
                with newlines, excluding the trailing copyright block, which
                embeds the current year and would otherwise change this number
                every January
              </span>
            </dd>
          </dl>

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
