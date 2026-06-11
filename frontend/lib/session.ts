"use client";

export const SESSION_STORAGE_KEY = "proposal-evaluator-session-id";
const SESSION_CHANGE_EVENT = "proposal-evaluator-session-id-change";

export function getOrCreateSessionId() {
  const existingSessionId = readPersistedSessionId();
  const nextSessionId = existingSessionId ?? crypto.randomUUID().replaceAll("-", "");

  persistSessionId(nextSessionId);
  return nextSessionId;
}

export function readSessionId() {
  return readPersistedSessionId();
}

export function replaceSessionId() {
  const nextSessionId = crypto.randomUUID().replaceAll("-", "");
  persistSessionId(nextSessionId);
  return nextSessionId;
}

export function subscribeToSessionIdChange(
  listener: (sessionId: string | null) => void,
) {
  const handleCustomEvent = (event: Event) => {
    const detail = (event as CustomEvent<{ sessionId: string | null }>).detail;
    listener(detail?.sessionId ?? readPersistedSessionId());
  };

  const handleStorageEvent = (event: StorageEvent) => {
    if (event.key !== SESSION_STORAGE_KEY) {
      return;
    }

    listener(event.newValue);
  };

  window.addEventListener(SESSION_CHANGE_EVENT, handleCustomEvent as EventListener);
  window.addEventListener("storage", handleStorageEvent);

  return () => {
    window.removeEventListener(SESSION_CHANGE_EVENT, handleCustomEvent as EventListener);
    window.removeEventListener("storage", handleStorageEvent);
  };
}

function readPersistedSessionId() {
  const localValue = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (localValue) {
    return localValue;
  }

  const sessionValue = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (sessionValue) {
    persistSessionId(sessionValue);
    return sessionValue;
  }

  return null;
}

function persistSessionId(sessionId: string) {
  window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  window.dispatchEvent(
    new CustomEvent(SESSION_CHANGE_EVENT, {
      detail: { sessionId },
    }),
  );
}
