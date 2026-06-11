import { ChunkDocumentViewer } from "../../../components/analysis/chunk-document-viewer/ChunkDocumentViewer";
import { publicApiBaseUrl } from "../../../lib/api-base";

const API_BASE_URL = publicApiBaseUrl;

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
