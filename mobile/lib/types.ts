/** Mirrors the backend response in backend/app/schema.py. */

export type Confidence = 'high' | 'medium' | 'low';

export type ImageQuality = 'good' | 'blurry' | 'too_far' | 'occluded' | 'dark';

export interface Candidate {
  common_name: string;
  scientific_name: string;
  genus: string;
  family?: string;
  confidence: Confidence;
  diagnostic_features?: string[];
}

export interface IdentifyResponse {
  is_plant: boolean;
  image_quality: ImageQuality;
  quality_hint: string | null;
  candidates: Candidate[];
  safety_note: string;
  meta?: {
    model?: string;
    elapsed_s?: number;
    metrics?: { cost?: number; predict_time?: number };
  };
}

export interface Care {
  light?: string;
  water?: string;
  humidity?: string;
  soil?: string;
  temperature?: string;
  toxicity?: string;
  common_problems?: string[];
}

export interface CareResponse {
  care: Care;
  safety_note: string;
}

/** A saved identification (local only, never leaves the device). */
export interface HistoryEntry {
  id: string;
  uri: string;
  at: number;
  /** Top candidate, denormalised so the list renders without walking `result`. */
  common_name: string;
  scientific_name: string;
  confidence: Confidence;
  /** Full response for reopening a saved result. */
  result: IdentifyResponse;
}
