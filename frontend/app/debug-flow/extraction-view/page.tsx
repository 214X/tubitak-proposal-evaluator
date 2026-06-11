import { RawOutputViewer } from "../../../components/analysis/raw-output-viewer/RawOutputViewer";
import { publicApiBaseUrl } from "../../../lib/api-base";

const API_BASE_URL = publicApiBaseUrl;

type ExtractionViewRouteProps = Readonly<{
  searchParams?: Promise<{
    sessionId?: string;
  }>;
}>;

export default async function ExtractionViewRoute({ searchParams }: ExtractionViewRouteProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  return (
    <RawOutputViewer
      apiBaseUrl={API_BASE_URL}
      initialSessionId={resolvedSearchParams?.sessionId ?? null}
      mode="extraction"
    />
  );
}
