import { EvaluationReportPage } from "../../../components/analysis/evaluation-report-page/EvaluationReportPage";
import { publicApiBaseUrl } from "../../../lib/api-base";

const API_BASE_URL = publicApiBaseUrl;

type EvaluationReportRouteProps = Readonly<{
  searchParams?: Promise<{
    sessionId?: string;
  }>;
}>;

export default async function EvaluationReportRoute({
  searchParams,
}: EvaluationReportRouteProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  return (
    <EvaluationReportPage
      apiBaseUrl={API_BASE_URL}
      initialSessionId={resolvedSearchParams?.sessionId ?? null}
    />
  );
}
