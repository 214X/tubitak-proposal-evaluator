"use client";

import type { FormEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { getOrCreateSessionId, replaceSessionId } from "../../lib/session";
import styles from "./upload-panel.module.css";

type UploadPanelProps = Readonly<{
  apiBaseUrl: string;
  onSessionReady?: (sessionId: string) => void;
  onUploadStateChange?: (uploadState: UploadState | null) => void;
}>;

export type UploadState = {
  session_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
};

const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx"];
const HEARTBEAT_INTERVAL_MS = 30000;

export function UploadPanel({
  apiBaseUrl,
  onSessionReady,
  onUploadStateChange,
}: UploadPanelProps) {
  const [sessionId, setSessionId] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isResettingSession, setIsResettingSession] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const nextSessionId = getOrCreateSessionId();
    setSessionId(nextSessionId);
  }, []);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    onSessionReady?.(sessionId);
    void loadCurrentUpload(sessionId, apiBaseUrl, setUploadState);
    void sendHeartbeat(sessionId, apiBaseUrl);

    const heartbeatId = window.setInterval(() => {
      void sendHeartbeat(sessionId, apiBaseUrl);
    }, HEARTBEAT_INTERVAL_MS);

    return () => {
      window.clearInterval(heartbeatId);
    };
  }, [apiBaseUrl, onSessionReady, sessionId]);

  useEffect(() => {
    onUploadStateChange?.(uploadState);
  }, [onUploadStateChange, uploadState]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setUploadError("Lütfen bir PDF veya Word belgesi seçin.");
      return;
    }

    if (!hasAllowedExtension(selectedFile.name)) {
      setUploadError("Sadece PDF, DOC ve DOCX dosyaları desteklenmektedir.");
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
        throw new Error(payload?.detail ?? `Yükleme başarısız oldu (Durum: ${response.status}).`);
      }

      const payload = (await response.json()) as UploadState;
      setUploadState(payload);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Yükleme başarısız oldu.");
    } finally {
      setIsUploading(false);
    }
  }

  function handleSelectedFileChange(file: File | null) {
    setSelectedFile(file);
    setUploadError("");
  }

  function clearSelectedFile() {
    setSelectedFile(null);
    setUploadError("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function handleResetSession() {
    if (!sessionId) {
      return;
    }

    setIsResettingSession(true);
    setUploadError("");

    try {
      await fetch(`${apiBaseUrl}/api/uploads/current`, {
        method: "DELETE",
        headers: {
          "X-Session-Id": sessionId,
        },
      }).catch(() => undefined);

      const nextSessionId = replaceSessionId();
      setSessionId(nextSessionId);
      setUploadState(null);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      setUploadError(
        error instanceof Error ? error.message : "Oturum sıfırlanamadı.",
      );
    } finally {
      setIsResettingSession(false);
    }
  }

  return (
    <form onSubmit={(event) => void handleUpload(event)} className={styles.uploadCard}>
      <div className={styles.uploadHeader}>
        <div>
          <p className={styles.sectionLabel}>DOKÜMAN YÜKLE</p>
          <p className={styles.sectionText}>Desteklenen formatlar: PDF, DOC, DOCX</p>
        </div>
      </div>

      <label className={styles.dropzone}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(event) => {
            handleSelectedFileChange(event.target.files?.[0] ?? null);
          }}
          className={styles.fileInput}
        />
        <span className={styles.dropzoneInner}>
          <span className={styles.dropzoneIcon}>
            <UploadIcon />
          </span>
          <span className={styles.dropzoneTitle}>Dosyayı buraya sürükleyin veya göz atın</span>
          <span className={styles.dropzoneNote}>Sadece tek bir dosya. PDF, DOC, DOCX</span>
        </span>
      </label>

      {selectedFile ? (
        <div className={styles.fileCard}>
          <div className={styles.fileMeta}>
            <div className={styles.fileTypeBadge}>{getFileBadgeLabel(selectedFile.name)}</div>
            <div>
              <p className={styles.fileName}>{selectedFile.name}</p>
              <p className={styles.fileSize}>{formatFileSize(selectedFile.size)}</p>
            </div>
          </div>
          <button
            type="button"
            className={styles.removeButton}
            onClick={clearSelectedFile}
            aria-label="Remove selected file"
          >
            <TrashIcon />
          </button>
        </div>
      ) : null}

      {uploadState ? (
        <div className={styles.uploadedState}>
          <p className={styles.uploadedLabel}>Mevcut oturum dosyası</p>
          <p className={styles.uploadedName}>{uploadState.file_name}</p>
        </div>
      ) : null}

      {uploadError ? <p className={styles.errorText}>{uploadError}</p> : null}

      <div className={styles.actionsRow}>
        <button
          type="submit"
          disabled={isUploading || isResettingSession || !sessionId || !selectedFile}
          className={styles.button}
        >
          {isUploading ? "Yükleniyor..." : "Dosya Yükle"}
        </button>

        {selectedFile ? (
          <button type="button" onClick={clearSelectedFile} className={styles.secondaryButton}>
            Dosyayı Kaldır
          </button>
        ) : null}

        <button
          type="button"
          onClick={() => void handleResetSession()}
          className={styles.tertiaryButton}
          disabled={isUploading || isResettingSession || !sessionId}
        >
          {isResettingSession ? "Oturum Sıfırlanıyor..." : "Session Sıfırla"}
        </button>
      </div>
    </form>
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
      throw new Error("Mevcut yükleme yüklenemedi.");
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

function getFileBadgeLabel(fileName: string) {
  const normalizedName = fileName.toLowerCase();

  if (normalizedName.endsWith(".pdf")) {
    return "PDF";
  }

  if (normalizedName.endsWith(".docx")) {
    return "DOCX";
  }

  if (normalizedName.endsWith(".doc")) {
    return "DOC";
  }

  return "DOSYA";
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 16V5" />
      <path d="m7 10 5-5 5 5" />
      <path d="M4 18.5a1.5 1.5 0 0 0 1.5 1.5h13a1.5 1.5 0 0 0 1.5-1.5" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 7h16" />
      <path d="M9 7V4.8h6V7" />
      <path d="M7.8 7l.7 11.2a1.5 1.5 0 0 0 1.5 1.4h4a1.5 1.5 0 0 0 1.5-1.4L16.2 7" />
      <path d="M10 10.5v5.5M14 10.5v5.5" />
    </svg>
  );
}
