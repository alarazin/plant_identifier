import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button } from '../components/Button';
import { CandidateCard, CandidateRow } from '../components/CandidateCard';
import { CareGrid } from '../components/CareGrid';
import { fetchCare } from '../lib/api';
import { colors, radius, space, type } from '../lib/theme';
import type { Candidate, Care, IdentifyResponse } from '../lib/types';

const QUALITY_COPY: Record<string, string> = {
  blurry: 'The photo is blurry',
  too_far: 'The subject is too far away',
  occluded: 'The plant is partly hidden',
  dark: 'The photo is too dark',
};

export function ResultScreen({
  uri,
  result,
  onNewPhoto,
  onBack,
}: {
  uri: string;
  result: IdentifyResponse;
  onNewPhoto: () => void;
  /** Allow returning home from both new and saved results. */
  onBack: () => void;
}) {
  const [selected, setSelected] = useState(0);
  const [careState, setCareState] = useState<{
    candidate: Candidate;
    care: Care | null;
    error: string | null;
  } | null>(null);

  const candidate = result.candidates[selected];
  // Hide the previous plant's advice immediately, even before the effect runs.
  const currentCare = careState?.candidate === candidate ? careState : null;

  useEffect(() => {
    let active = true;
    setCareState(null);
    if (!candidate) return;

    const loadCare = async () => {
      try {
        const res = await fetchCare(candidate.scientific_name, candidate.common_name);
        if (active) setCareState({ candidate, care: res.care, error: null });
      } catch (err: any) {
        if (active) {
          setCareState({
            candidate,
            care: null,
            error: err?.message ?? 'Could not load care information.',
          });
        }
      }
    };

    loadCare();
    // Ignore responses after candidate changes or screen unmount.
    return () => {
      active = false;
    };
  }, [candidate]);

  // ---- not a plant -------------------------------------------------------
  if (!result.is_plant || result.candidates.length === 0) {
    return (
      <ScrollView contentContainerStyle={styles.centered}>
        <Image source={{ uri }} style={styles.thumb} />
        <Text style={styles.emptyTitle}>That doesn&apos;t look like a plant</Text>
        <Text style={styles.emptyBody}>
          {result.quality_hint ??
            'Point the camera at a leaf, flower or whole plant and try again.'}
        </Text>
        <Button label="Take another photo" onPress={onNewPhoto} />
        <Button label="Back to home" variant="ghost" onPress={onBack} />
      </ScrollView>
    );
  }

  const alternatives = result.candidates.filter((_, i) => i !== selected);
  const qualityIssue = result.image_quality !== 'good' ? result.image_quality : null;

  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.heroWrap}>
          <Image source={{ uri }} style={styles.hero} resizeMode="cover" />
          <HeroFade />
        </View>

        {/* Show retake guidance for poor image quality. */}
        {qualityIssue && (
          <View style={styles.qualityBanner}>
            <Text style={styles.qualityTitle}>
              {QUALITY_COPY[qualityIssue] ?? 'The photo may be hard to read'}
            </Text>
            {!!result.quality_hint && (
              <Text style={styles.qualityHint}>{result.quality_hint}</Text>
            )}
            <Button label="Retake for a better match" variant="secondary" onPress={onNewPhoto} />
          </View>
        )}

        {candidate && <CandidateCard candidate={candidate} />}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>CARE</Text>
          <CareGrid
            care={currentCare?.care ?? null}
            loading={!!candidate && !currentCare}
            error={currentCare?.error ?? null}
          />
        </View>

        {alternatives.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>NOT RIGHT? ALSO POSSIBLE</Text>
            <Text style={styles.sectionNote}>
              Tap to switch — care information updates too.
            </Text>
            <View style={styles.altList}>
              {result.candidates.map((c, i) =>
                i === selected ? null : (
                  <CandidateRow key={i} candidate={c} onPress={() => setSelected(i)} />
                ),
              )}
            </View>
          </View>
        )}

        <Text style={styles.safety}>{result.safety_note}</Text>

        <Button label="Identify another plant" onPress={onNewPhoto} style={styles.cta} />
      </ScrollView>

      {/* Keep the back button visible while scrolling. */}
      <Pressable
        onPress={onBack}
        hitSlop={space.md}
        style={({ pressed }) => [styles.backButton, pressed && styles.backPressed]}
      >
        <Text style={styles.backIcon}>‹</Text>
      </Pressable>
    </View>
  );
}

/** Fade the bottom of the photo into the page background. */
function HeroFade() {
  return (
    <LinearGradient
      style={styles.heroFade}
      colors={[`${colors.bg}00`, `${colors.bg}66`, colors.bg]}
      locations={[0, 0.55, 1]}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: space.lg, paddingTop: 0, gap: space.lg, paddingBottom: space.xxl },

  heroWrap: {
    height: 300,
    marginHorizontal: -space.lg,
    // Keep the first card below the photo and quality banner.
    marginBottom: 0,
  },
  hero: { width: '100%', height: '100%' },
  heroFade: {
    pointerEvents: 'none',
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: 120,
  },

  qualityBanner: {
    backgroundColor: `${colors.warn}14`,
    borderWidth: 1,
    borderColor: `${colors.warn}44`,
    borderRadius: radius.md,
    padding: space.lg,
    gap: space.sm,
  },
  qualityTitle: { ...type.bodyStrong, color: colors.warn },
  qualityHint: { ...type.small, color: colors.textMuted, lineHeight: 20 },

  section: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space.lg,
    gap: space.md,
  },
  sectionTitle: { ...type.caption, color: colors.textFaint },
  sectionNote: { ...type.small, color: colors.textFaint, marginTop: -space.sm },
  altList: { gap: space.sm },

  safety: {
    ...type.small,
    color: colors.textFaint,
    lineHeight: 19,
    textAlign: 'center',
    paddingHorizontal: space.sm,
  },
  cta: { marginTop: space.sm },

  backButton: {
    position: 'absolute',
    top: space.md,
    left: space.lg,
    width: 36,
    height: 36,
    borderRadius: radius.pill,
    // Translucent: it sits over the photo, which can be any colour.
    backgroundColor: colors.scrim,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backPressed: { opacity: 0.6 },
  backIcon: { color: colors.onImage, fontSize: 28, lineHeight: 30, marginTop: -4 },

  centered: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.lg,
    padding: space.xl,
    backgroundColor: colors.bg,
  },
  thumb: { width: 140, height: 140, borderRadius: radius.lg, opacity: 0.5 },
  emptyTitle: { ...type.title, color: colors.text, textAlign: 'center' },
  emptyBody: {
    ...type.body,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 22,
  },
});
