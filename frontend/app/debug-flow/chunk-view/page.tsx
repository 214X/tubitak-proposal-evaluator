import { ChunkDocumentViewer } from "../../../components/analysis/chunk-document-viewer/ChunkDocumentViewer";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type ChunkViewRouteProps = Readonly<{
  searchParams?: Promise<{
    sessionId?: string;
  }>;
}>;

export default async function ChunkViewRoute({ searchParams }: ChunkViewRouteProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;

  return (
    <ChunkDocumentViewer
      apiBaseUrl={API_BASE_URL}
      initialSessionId={resolvedSearchParams?.sessionId ?? null}
    />
  );
}
