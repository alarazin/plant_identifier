import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import { Platform } from 'react-native';

import { API_BASE, MAX_IMAGE_EDGE, REQUEST_TIMEOUT_MS } from './config';
import type { CareResponse, IdentifyResponse } from './types';

export class ApiError extends Error {
  constructor(message: string, readonly kind: 'network' | 'server' | 'timeout') {
    super(message);
  }
}

/** Resize and encode the image as JPEG before upload. */
async function prepareImage(uri: string): Promise<string> {
  try {
    const context = ImageManipulator.manipulate(uri);
    context.resize({ width: MAX_IMAGE_EDGE });
    const rendered = await context.renderAsync();
    const saved = await rendered.saveAsync({
      format: SaveFormat.JPEG,
      compress: 0.8,
    });
    return saved.uri;
  } catch {
    // If local resizing fails, send the original image; the backend resizes it.
    return uri;
  }
}

/** Attach a Blob on web or a file descriptor on native.
 * Native uploads require EXPO_PUBLIC_USE_RN_FETCH=1. */
async function appendImage(form: FormData, uri: string, signal: AbortSignal): Promise<void> {
  if (Platform.OS === 'web') {
    const blob = await (await fetch(uri, { signal })).blob();
    form.append('image', blob, 'photo.jpg');
    return;
  }
  form.append('image', { uri, name: 'photo.jpg', type: 'image/jpeg' } as any);
}

function throwIfAborted(signal?: AbortSignal): void {
  if (!signal?.aborted) return;
  const error = new Error('Request cancelled.');
  error.name = 'AbortError';
  throw error;
}

async function withTimeout<T>(
  run: (signal: AbortSignal) => Promise<T>,
  callerSignal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const onCancel = () => controller.abort();
  callerSignal?.addEventListener('abort', onCancel);
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    throwIfAborted(callerSignal);
    const result = await run(controller.signal);
    throwIfAborted(callerSignal);
    return result;
  } catch (err: any) {
    // User cancellation is silent in the app; a deadline expiry remains an error.
    throwIfAborted(callerSignal);
    if (err?.name === 'AbortError') {
      throw new ApiError('That took too long. Check the backend is running.', 'timeout');
    }
    if (err instanceof ApiError) throw err;

    // Treat fetch TypeError as a connection failure; preserve other error messages.
    if (err instanceof TypeError) {
      throw new ApiError(
        `Cannot reach the backend at ${API_BASE}. Is it running, and is this device on the same network?`,
        'network',
      );
    }
    throw new ApiError(err?.message ?? String(err), 'server');
  } finally {
    clearTimeout(timer);
    callerSignal?.removeEventListener('abort', onCancel);
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail ?? body);
  } catch {
    return `Server returned ${res.status}`;
  }
}

/** Progress stages for image preparation and identification. */
export type Stage = 'preparing' | 'identifying';

export async function identify(
  photoUri: string,
  onStage?: (stage: Stage) => void,
  signal?: AbortSignal,
): Promise<IdentifyResponse> {
  throwIfAborted(signal);
  onStage?.('preparing');
  const prepared = await prepareImage(photoUri);
  // Image manipulation cannot be aborted, but cancelled work must never upload.
  throwIfAborted(signal);
  onStage?.('identifying');

  return withTimeout(async (requestSignal) => {
    const form = new FormData();
    await appendImage(form, prepared, requestSignal);
    throwIfAborted(requestSignal);

    const res = await fetch(`${API_BASE}/identify`, {
      method: 'POST',
      body: form,
      signal: requestSignal,
    });

    if (!res.ok) throw new ApiError(await readError(res), 'server');
    return (await res.json()) as IdentifyResponse;
  }, signal);
}

export async function fetchCare(
  scientificName: string,
  commonName: string,
): Promise<CareResponse> {
  return withTimeout(async (signal) => {
    const res = await fetch(`${API_BASE}/care`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scientific_name: scientificName, common_name: commonName }),
      signal,
    });

    if (!res.ok) throw new ApiError(await readError(res), 'server');
    return (await res.json()) as CareResponse;
  });
}
