import { RawOutputViewer } from "../../../components/analysis/raw-output-viewer/RawOutputViewer";
import { publicApiBaseUrl } from "../../../lib/api-base";

const API_BASE_URL = publicApiBaseUrl;

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
