"use client";

export const SESSION_STORAGE_KEY = "proposal-evaluator-session-id";

export function getOrCreateSessionId() {
  const existingSessionId = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  const nextSessionId = existingSessionId ?? crypto.randomUUID().replaceAll("-", "");

  window.sessionStorage.setItem(SESSION_STORAGE_KEY, nextSessionId);
  return nextSessionId;
}

export function readSessionId() {
  return window.sessionStorage.getItem(SESSION_STORAGE_KEY);
}

export function replaceSessionId() {
  const nextSessionId = crypto.randomUUID().replaceAll("-", "");
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, nextSessionId);
  return nextSessionId;
}
