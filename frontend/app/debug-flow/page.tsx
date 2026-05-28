import { DebugFlowPage } from "../../components/pages/debug-flow/DebugFlowPage";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type HealthStatus = {
  status: string;
  service: string;
  version: string;
};

async function getHealthStatus(): Promise<HealthStatus> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
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

export default async function DebugFlowRoute() {
  const health = await getHealthStatus();
  return <DebugFlowPage health={health} apiBaseUrl={API_BASE_URL} />;
}
