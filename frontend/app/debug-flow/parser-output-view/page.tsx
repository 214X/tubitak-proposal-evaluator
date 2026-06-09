import { RawOutputViewer } from "../../../components/analysis/raw-output-viewer/RawOutputViewer";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type ParserOutputViewRouteProps = Readonly<{
  searchParams?: Promise<{
    sessionId?: string;
  }>;
}>;

export default async function ParserOutputViewRoute({
  searchParams,
}: ParserOutputViewRouteProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;

  return (
    <RawOutputViewer
      apiBaseUrl={API_BASE_URL}
      initialSessionId={resolvedSearchParams?.sessionId ?? null}
      mode="parser"
    />
  );
}
