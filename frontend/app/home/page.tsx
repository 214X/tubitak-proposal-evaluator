import { Homepage } from "../../components/pages/homepage";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getHealthStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`);
    }

    return response.json() as Promise<{
      status: string;
      service: string;
      version: string;
    }>;
  } catch (error) {
    return {
      status: "unreachable",
      service: "API connection failed",
      version: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

export default async function HomePage() {
  const health = await getHealthStatus();
  return <Homepage health={health} />;
}
