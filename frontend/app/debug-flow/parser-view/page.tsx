import { ParserDocumentViewer } from "../../../components/analysis/parser-document-viewer/ParserDocumentViewer";
import { publicApiBaseUrl } from "../../../lib/api-base";

const API_BASE_URL = publicApiBaseUrl;

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
