import { EvaluationPage } from "../../components/pages/evaluation/EvaluationPage";
import { internalApiBaseUrl, publicApiBaseUrl } from "../../lib/api-base";

const API_BASE_URL = publicApiBaseUrl;
const INTERNAL_API_BASE_URL = internalApiBaseUrl;

type HealthStatus = {
  status: string;
  service: string;
  version: string;
};

async function getHealthStatus(): Promise<HealthStatus> {
  try {
    const response = await fetch(`${INTERNAL_API_BASE_URL}/api/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`);
    }

    return response.json() as Promise<HealthStatus>;
  } catch (error) {
    return {
      status: "unreachable",
      service: "API connection failed",
      version: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

export default async function EvaluationRoute() {
  const health = await getHealthStatus();
  return <EvaluationPage health={health} apiBaseUrl={API_BASE_URL} />;
}
