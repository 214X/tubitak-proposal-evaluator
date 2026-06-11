import { EmbeddingSearchViewer } from "../../../components/analysis/embedding-search-viewer/EmbeddingSearchViewer";
import { publicApiBaseUrl } from "../../../lib/api-base";

const API_BASE_URL = publicApiBaseUrl;

type EmbeddingViewRouteProps = Readonly<{
  searchParams?: Promise<{
    sessionId?: string;
  }>;
}>;

export default async function EmbeddingViewRoute({
  searchParams,
}: EmbeddingViewRouteProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;

  return (
    <EmbeddingSearchViewer
      apiBaseUrl={API_BASE_URL}
      initialSessionId={resolvedSearchParams?.sessionId ?? null}
    />
  );
}
