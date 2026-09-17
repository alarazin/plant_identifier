import AsyncStorage from '@react-native-async-storage/async-storage';

import type { HistoryEntry, IdentifyResponse } from './types';

/** Versioned storage key for saved identifications. */
const KEY = 'history.v1';

/** Previous storage keys, checked newest first during migration. */
const LEGACY_KEYS = ['plantkey.history.v1', 'fieldnote.history.v1'];

/** Keep the 50 most recent results. Cached photos may expire separately. */
const LIMIT = 50;

/** Check saved records before displaying them. */
function isEntry(value: unknown): value is HistoryEntry {
  if (typeof value !== 'object' || value === null) return false;
  const e = value as Partial<HistoryEntry>;
  return (
    typeof e.id === 'string' &&
    typeof e.uri === 'string' &&
    typeof e.at === 'number' &&
    typeof e.common_name === 'string' &&
    typeof e.scientific_name === 'string' &&
    typeof e.result === 'object' &&
    e.result !== null &&
    Array.isArray(e.result.candidates)
  );
}

/** Newest first. */
export async function loadHistory(): Promise<HistoryEntry[]> {
  try {
    const raw = (await AsyncStorage.getItem(KEY)) ?? (await migrateLegacy());
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isEntry) : [];
  } catch {
    // Return an empty history if storage cannot be read.
    return [];
  }
}

/** Save a plant identification and return the updated list. */
export async function saveIdentification(
  uri: string,
  result: IdentifyResponse,
): Promise<HistoryEntry[]> {
  const top = result.candidates[0];
  const existing = await loadHistory();
  if (!result.is_plant || !top) return existing;

  const entry: HistoryEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    uri,
    at: Date.now(),
    common_name: top.common_name,
    scientific_name: top.scientific_name,
    confidence: top.confidence,
    result,
  };

  const next = [entry, ...existing].slice(0, LIMIT);
  await persist(next);
  return next;
}

export async function clearHistory(): Promise<void> {
  try {
    await AsyncStorage.removeItem(KEY);
  } catch {
    // Nothing useful to do, and the caller has already cleared its own state.
  }
}

/** Move saved entries from an older key and remove the old keys. */
async function migrateLegacy(): Promise<string | null> {
  let found: string | null = null;

  for (const key of LEGACY_KEYS) {
    const value = await AsyncStorage.getItem(key);
    // Use the newest store and remove all old keys.
    if (value && !found) found = value;
    if (value) await AsyncStorage.removeItem(key);
  }

  if (found) await AsyncStorage.setItem(KEY, found);
  return found;
}

async function persist(entries: HistoryEntry[]): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(entries));
  } catch {
    // A storage failure should not discard the identification on screen.
  }
}
