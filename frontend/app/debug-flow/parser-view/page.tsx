import { ParserDocumentViewer } from "../../../components/analysis/parser-document-viewer/ParserDocumentViewer";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type ParserViewRouteProps = Readonly<{
  searchParams?: Promise<{
    sessionId?: string;
  }>;
}>;

export default async function ParserViewRoute({ searchParams }: ParserViewRouteProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  return (
    <ParserDocumentViewer
      apiBaseUrl={API_BASE_URL}
      initialSessionId={resolvedSearchParams?.sessionId ?? null}
    />
  );
}
