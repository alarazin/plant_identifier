import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, space, type } from '../lib/theme';
import type { Candidate } from '../lib/types';
import { ConfidenceChip } from './ConfidenceChip';

/** Plant candidate with species, genus, family and visible features. */
export function CandidateCard({ candidate }: { candidate: Candidate }) {
  const abstained =
    !candidate.scientific_name ||
    candidate.scientific_name.toLowerCase() === 'uncertain';

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.common}>{candidate.common_name}</Text>
        <ConfidenceChip level={candidate.confidence} />
      </View>

      {abstained ? (
        // Show a readable label when the species is uncertain.
        <Text style={styles.abstained}>
          Not certain of the exact species — but it&apos;s in the {candidate.genus} group
        </Text>
      ) : (
        <Text style={styles.scientific}>{candidate.scientific_name}</Text>
      )}

      <View style={styles.taxonomy}>
        {!!candidate.genus && <Taxon label="Genus" value={candidate.genus} />}
        {!!candidate.family && <Taxon label="Family" value={candidate.family} />}
      </View>

      {!!candidate.diagnostic_features?.length && (
        <View style={styles.why}>
          <Text style={styles.whyTitle}>WHY WE THINK SO</Text>
          {candidate.diagnostic_features.map((f, i) => (
            <View key={i} style={styles.featureRow}>
              <Text style={styles.bullet}>·</Text>
              <Text style={styles.feature}>{f}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

function Taxon({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.taxon}>
      <Text style={styles.taxonLabel}>{label}</Text>
      <Text style={styles.taxonValue}>{value}</Text>
    </View>
  );
}

/** Compact row used in the "other possibilities" list. */
export function CandidateRow({
  candidate,
  onPress,
}: {
  candidate: Candidate;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
    >
      <View style={styles.rowText}>
        <Text style={styles.rowCommon}>{candidate.common_name}</Text>
        <Text style={styles.rowSci}>{candidate.scientific_name}</Text>
      </View>
      <ConfidenceChip level={candidate.confidence} small />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space.lg,
    gap: space.md,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: space.md,
  },
  common: { ...type.display, color: colors.text, flex: 1 },
  scientific: { ...type.mono, color: colors.accent, marginTop: -space.sm },
  abstained: { ...type.small, color: colors.warn, marginTop: -space.sm, lineHeight: 19 },

  taxonomy: { flexDirection: 'row', gap: space.xl },
  taxon: { gap: 2 },
  taxonLabel: { ...type.caption, color: colors.textFaint },
  taxonValue: { ...type.bodyStrong, color: colors.textMuted },

  why: {
    gap: space.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: space.md,
  },
  whyTitle: { ...type.caption, color: colors.textFaint },
  featureRow: { flexDirection: 'row', gap: space.sm },
  bullet: { color: colors.accentDim, ...type.body },
  feature: { ...type.small, color: colors.textMuted, flex: 1, lineHeight: 20 },

  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: space.md,
  },
  rowPressed: { opacity: 0.6 },
  rowText: { flex: 1, gap: 2 },
  rowCommon: { ...type.bodyStrong, color: colors.text },
  rowSci: { ...type.small, color: colors.textFaint, fontStyle: 'italic' },
});
