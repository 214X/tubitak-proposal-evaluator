"use client";

import { useEffect, useMemo, useState } from "react";

import {
  type AnalysisState,
  type HeadingHierarchyNode,
  type ParserListContent,
  type ParserOutput,
  type ParserStreamItem,
  fetchCurrentAnalysis,
} from "../../../lib/analysis";
import { readSessionId } from "../../../lib/session";
import styles from "./parser-document-viewer.module.css";

type ParserDocumentViewerProps = Readonly<{
  apiBaseUrl: string;
  initialSessionId?: string | null;
}>;

export function ParserDocumentViewer({
  apiBaseUrl,
  initialSessionId = null,
}: ParserDocumentViewerProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [analysisState, setAnalysisState] = useState<AnalysisState | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const nextSessionId = initialSessionId ?? readSessionId();
    setSessionId(nextSessionId);

    if (!nextSessionId) {
      setError("Aktif bir oturum bulunamadı.");
      return;
    }

    let cancelled = false;
    void fetchCurrentAnalysis(apiBaseUrl, nextSessionId)
      .then((nextState) => {
        if (!cancelled) {
          setAnalysisState(nextState);
        }
      })
      .catch((currentError) => {
        if (!cancelled) {
          setError(
            currentError instanceof Error
              ? currentError.message
              : "Parser sonucu yüklenemedi.",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, initialSessionId]);

  const parserOutput = analysisState?.parser_output ?? null;
  const streamByRef = useMemo(() => {
    if (!parserOutput) {
      return new Map<string, ParserStreamItem>();
    }

    return new Map(parserOutput.content_stream.map((item) => [item.ref, item]));
  }, [parserOutput]);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Parser Viewer</p>
          <h1 className={styles.title}>Belge Görünümü</h1>
        </div>
        {sessionId ? <p className={styles.session}>Session: {sessionId}</p> : null}
      </header>

      {error ? <p className={styles.error}>{error}</p> : null}

      <section className={styles.canvas}>
        {parserOutput ? (
          <article className={styles.document}>
            <div className={styles.documentHeader}>
              <p className={styles.documentMetaLabel}>Hazırlanan belge görünümü</p>
              <h2 className={styles.documentTitle}>{parserOutput.document.file_name}</h2>
              <p className={styles.documentMeta}>
                {parserOutput.document.page_count} sayfa • {parserOutput.heading_hierarchy.length} kök başlık
              </p>
            </div>

            <div className={styles.documentBody}>
              {parserOutput.heading_hierarchy.map((heading) => (
                <DocumentHeadingSection
                  key={heading.id}
                  heading={heading}
                  streamByRef={streamByRef}
                />
              ))}
            </div>
          </article>
        ) : (
          <div className={styles.emptyState}>
            <div className={styles.emptyLine} />
            <div className={styles.emptyLineLong} />
            <div className={styles.emptySheet} />
          </div>
        )}
      </section>
    </main>
  );
}

function DocumentHeadingSection({
  heading,
  streamByRef,
}: Readonly<{
  heading: HeadingHierarchyNode;
  streamByRef: Map<string, ParserStreamItem>;
}>) {
  const orderedEntries = [
    ...heading.content_refs
      .map((ref) => streamByRef.get(ref))
      .filter((item): item is ParserStreamItem => Boolean(item))
      .map((item) => ({ order: item.order, kind: "content" as const, item })),
    ...heading.children.map((child) => ({ order: child.stream_order, kind: "heading" as const, child })),
  ].sort((left, right) => left.order - right.order);

  return (
    <section className={styles.section}>
      <div className={styles.sectionHeading}>
        <p className={styles.sectionCode}>{heading.code}</p>
        <h3 className={styles.sectionTitle}>{heading.title ?? heading.full_text}</h3>
        <p className={styles.sectionMeta}>
          Sayfa {heading.page_start ?? "?"}
          {heading.page_end && heading.page_end !== heading.page_start ? ` - ${heading.page_end}` : ""}
        </p>
      </div>

      <div className={styles.sectionContent}>
        {orderedEntries.map((entry, index) => {
          if (entry.kind === "content") {
            return <DocumentContentBlock key={`${entry.item.ref}-${index}`} item={entry.item} />;
          }

          return (
            <div key={entry.child.id} className={styles.childSection}>
              <DocumentHeadingSection heading={entry.child} streamByRef={streamByRef} />
            </div>
          );
        })}
      </div>
    </section>
  );
}

function DocumentContentBlock({ item }: Readonly<{ item: ParserStreamItem }>) {
  if (item.item_type === "text" && typeof item.content === "string") {
    return <p className={styles.paragraph}>{item.content}</p>;
  }

  if (item.item_type === "table" && isDoclingTableData(item.content)) {
    return <DocumentTable table={item.content} />;
  }

  if (item.item_type === "group" && isNormalizedListContent(item.content)) {
    return <DocumentList items={item.content.items} />;
  }

  return (
    <pre className={styles.fallbackBlock}>{JSON.stringify(item.content, null, 2)}</pre>
  );
}

function DocumentTable({
  table,
}: Readonly<{
  table: {
    grid?: Array<Array<{ text?: string } | null>>;
  };
}>) {
  const rows = table.grid ?? [];
  if (!rows.length) {
    return <div className={styles.tableEmpty}>Tablo içeriği boş.</div>;
  }

  const headerRow = rows[0] ?? [];
  const bodyRows = rows.slice(1);

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {headerRow.map((cell, index) => (
              <th key={`head-${index}`}>{cell?.text ?? ""}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, rowIndex) => (
            <tr key={`row-${rowIndex}`}>
              {row.map((cell, cellIndex) => (
                <td key={`cell-${rowIndex}-${cellIndex}`}>{cell?.text ?? ""}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DocumentList({ items }: Readonly<{ items: string[] }>) {
  if (!items.length) {
    return null;
  }

  return (
    <ul className={styles.list}>
      {items.map((item, index) => (
        <li key={`${index}-${item.slice(0, 24)}`} className={styles.listItem}>
          {item}
        </li>
      ))}
    </ul>
  );
}

function isDoclingTableData(value: unknown): value is { grid?: Array<Array<{ text?: string } | null>> } {
  return typeof value === "object" && value !== null;
}

function isNormalizedListContent(value: unknown): value is ParserListContent {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Partial<ParserListContent>;
  return candidate.type === "list" && Array.isArray(candidate.items);
}
