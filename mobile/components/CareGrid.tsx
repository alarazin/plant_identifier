import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { colors, radius, space, type } from '../lib/theme';
import type { Care } from '../lib/types';

const FIELDS: { key: keyof Care; label: string; icon: string }[] = [
  { key: 'light', label: 'Light', icon: '☀' },
  { key: 'water', label: 'Water', icon: '◇' },
  { key: 'humidity', label: 'Humidity', icon: '≈' },
  { key: 'soil', label: 'Soil', icon: '▦' },
  { key: 'temperature', label: 'Temperature', icon: '◐' },
];

export function CareGrid({
  care,
  loading,
  error,
}: {
  care: Care | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <View style={styles.placeholder}>
        <ActivityIndicator color={colors.accentDim} />
        <Text style={styles.placeholderText}>Looking up care needs…</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.placeholder}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  if (!care) return null;

  return (
    <View style={styles.wrap}>
      {FIELDS.filter((f) => !!care[f.key]).map((f) => (
        <View key={f.key} style={styles.item}>
          <Text style={styles.icon}>{f.icon}</Text>
          <View style={styles.itemText}>
            <Text style={styles.label}>{f.label}</Text>
            <Text style={styles.value}>{care[f.key] as string}</Text>
          </View>
        </View>
      ))}

      {!!care.toxicity && (
        // Show toxicity separately from routine care advice.
        <View style={styles.toxicity}>
          <Text style={styles.toxicityLabel}>TOXICITY</Text>
          <Text style={styles.toxicityValue}>{care.toxicity}</Text>
        </View>
      )}

      {!!care.common_problems?.length && (
        <View style={styles.problems}>
          <Text style={styles.label}>Watch for</Text>
          {care.common_problems.map((p, i) => (
            <View key={i} style={styles.problemRow}>
              <Text style={styles.bullet}>·</Text>
              <Text style={styles.value}>{p}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: space.md },
  item: { flexDirection: 'row', gap: space.md, alignItems: 'flex-start' },
  icon: {
    fontSize: 16,
    color: colors.accentDim,
    width: 22,
    textAlign: 'center',
    marginTop: 1,
  },
  itemText: { flex: 1, gap: 2 },
  label: { ...type.caption, color: colors.textFaint, textTransform: 'uppercase' },
  value: { ...type.small, color: colors.textMuted, lineHeight: 20, flex: 1 },

  toxicity: {
    backgroundColor: `${colors.warn}14`,
    borderLeftWidth: 2,
    borderLeftColor: colors.warn,
    borderRadius: radius.sm,
    padding: space.md,
    gap: space.xs,
    marginTop: space.xs,
  },
  toxicityLabel: { ...type.caption, color: colors.warn },
  toxicityValue: { ...type.small, color: colors.text, lineHeight: 20 },

  problems: { gap: space.xs, marginTop: space.xs },
  problemRow: { flexDirection: 'row', gap: space.sm },
  bullet: { color: colors.accentDim, ...type.body },

  placeholder: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    paddingVertical: space.lg,
  },
  placeholderText: { ...type.small, color: colors.textFaint },
  errorText: { ...type.small, color: colors.low },
});
