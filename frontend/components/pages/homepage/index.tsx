"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import styles from "./homepage.module.css";

type HomepageProps = {
  health: {
    status: string;
    service: string;
    version: string;
  };
  apiBaseUrl: string;
};

type UploadState = {
  session_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
};

const SESSION_STORAGE_KEY = "proposal-evaluator-session-id";
const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx"];
const HEARTBEAT_INTERVAL_MS = 30000;

export function Homepage({ health, apiBaseUrl }: HomepageProps) {
  const isHealthy = health.status === "ok";
  const [sessionId, setSessionId] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    const existingSessionId = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    const nextSessionId = existingSessionId ?? crypto.randomUUID().replaceAll("-", "");

    window.sessionStorage.setItem(SESSION_STORAGE_KEY, nextSessionId);
    setSessionId(nextSessionId);
    void loadCurrentUpload(nextSessionId, apiBaseUrl, setUploadState);
    void sendHeartbeat(nextSessionId, apiBaseUrl);

    const heartbeatId = window.setInterval(() => {
      void sendHeartbeat(nextSessionId, apiBaseUrl);
    }, HEARTBEAT_INTERVAL_MS);

    return () => {
      window.clearInterval(heartbeatId);
    };
  }, [apiBaseUrl]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setUploadError("Please choose a PDF or Word document.");
      return;
    }

    if (!hasAllowedExtension(selectedFile.name)) {
      setUploadError("Only PDF, DOC, and DOCX files are supported.");
      return;
    }

    setUploadError("");
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${apiBaseUrl}/api/uploads`, {
        method: "POST",
        headers: {
          "X-Session-Id": sessionId,
        },
        body: formData,
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(payload?.detail ?? `Upload failed with status ${response.status}.`);
      }

      const payload = (await response.json()) as UploadState;
      setUploadState(payload);
      setSelectedFile(null);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <main className={styles.main}>
      <section className={styles.panel}>
        <div>
          <p className={styles.eyebrow}>TUBITAK Proposal Evaluator</p>
          <h1 className={styles.title}>Upload service checkpoint</h1>
          <p className={styles.description}>
            Upload one PDF or Word file per browser session. The backend keeps the
            active file isolated per session while the page stays active.
          </p>
        </div>

        <div className={styles.metricsGrid}>
          <MetricCard
            label="Status"
            value={health.status}
            accentClassName={isHealthy ? styles.metricHealthy : styles.metricDanger}
          />
          <MetricCard label="Service" value={health.service} accentClassName={styles.metricInfo} />
          <MetricCard label="Version" value={health.version} accentClassName={styles.metricWarning} />
        </div>

        <form onSubmit={(event) => void handleUpload(event)} className={styles.formCard}>
          <div>
            <p className={styles.sectionLabel}>Upload document</p>
            <p className={styles.sectionText}>Accepted formats: PDF, DOC, DOCX</p>
          </div>

          <input
            type="file"
            accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              setSelectedFile(file);
              setUploadError("");
            }}
            className={styles.fileInput}
          />

          <button type="submit" disabled={isUploading || !sessionId} className={styles.button}>
            {isUploading ? "Uploading..." : "Upload file"}
          </button>

          {selectedFile ? (
            <p className={styles.helperText}>Selected file: {selectedFile.name}</p>
          ) : null}

          {uploadError ? <p className={styles.errorText}>{uploadError}</p> : null}
        </form>

        <section className={styles.sessionCard}>
          <p className={styles.sessionLabel}>Active session upload</p>

          {uploadState ? (
            <div className={styles.sessionDetails}>
              <p className={styles.detailText}>
                <strong>File:</strong> {uploadState.file_name}
              </p>
              <p className={styles.detailText}>
                <strong>Type:</strong> {uploadState.content_type}
              </p>
              <p className={styles.detailText}>
                <strong>Size:</strong> {formatFileSize(uploadState.size_bytes)}
              </p>
              <p className={styles.detailText}>
                <strong>Uploaded at:</strong> {new Date(uploadState.uploaded_at).toLocaleString()}
              </p>
            </div>
          ) : (
            <p className={styles.emptyText}>No file is currently stored for this browser session.</p>
          )}
        </section>
      </section>
    </main>
  );
}

type MetricCardProps = {
  label: string;
  value: string;
  accentClassName: string;
};

function MetricCard({ label, value, accentClassName }: MetricCardProps) {
  return (
    <article className={`${styles.metricCard} ${accentClassName}`}>
      <p className={styles.metricLabel}>{label}</p>
      <p className={styles.metricValue}>{value}</p>
    </article>
  );
}

function hasAllowedExtension(fileName: string) {
  const normalizedName = fileName.toLowerCase();
  return ALLOWED_EXTENSIONS.some((extension) => normalizedName.endsWith(extension));
}

async function loadCurrentUpload(
  nextSessionId: string,
  apiBaseUrl: string,
  setUploadState: (value: UploadState | null) => void,
) {
  try {
    const response = await fetch(`${apiBaseUrl}/api/uploads/current`, {
      headers: {
        "X-Session-Id": nextSessionId,
      },
    });

    if (response.status === 404) {
      setUploadState(null);
      return;
    }

    if (!response.ok) {
      throw new Error("Unable to load current upload.");
    }

    const payload = (await response.json()) as UploadState;
    setUploadState(payload);
  } catch {
    setUploadState(null);
  }
}

async function sendHeartbeat(sessionId: string, apiBaseUrl: string) {
  await fetch(`${apiBaseUrl}/api/uploads/current/heartbeat`, {
    method: "POST",
    headers: {
      "X-Session-Id": sessionId,
    },
  }).catch(() => undefined);
}

function formatFileSize(sizeBytes: number) {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }

  const sizeKilobytes = sizeBytes / 1024;
  return `${sizeKilobytes.toFixed(1)} KB`;
}
