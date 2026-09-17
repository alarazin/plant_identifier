import Constants from 'expo-constants';
import { Platform } from 'react-native';

/** Use the Metro host for the backend address. Override with EXPO_PUBLIC_API_BASE. */
function resolveApiBase(): string {
  const explicit = process.env.EXPO_PUBLIC_API_BASE;
  if (explicit) return explicit.replace(/\/$/, '');

  // Use localhost for browser development on the backend machine.
  if (Platform.OS === 'web') return 'http://localhost:8000';

  const host = Constants.expoConfig?.hostUri?.split(':')[0];
  if (host) return `http://${host}:8000`;

  return 'http://localhost:8000';
}

export const API_BASE = resolveApiBase();

/** Identification is a 3-hop server round-trip (upload, predict, poll). */
export const REQUEST_TIMEOUT_MS = 60_000;

/** Match the backend's maximum image size. */
export const MAX_IMAGE_EDGE = 1024;
