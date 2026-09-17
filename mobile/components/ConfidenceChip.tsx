import { StyleSheet, Text, View } from 'react-native';

import { colors, confidenceColor, confidenceLabel, radius, space, type } from '../lib/theme';
import type { Confidence } from '../lib/types';

export function ConfidenceChip({ level, small }: { level: Confidence; small?: boolean }) {
  const tint = confidenceColor(level);
  return (
    <View
      style={[
        styles.chip,
        { borderColor: tint, backgroundColor: `${tint}1A` },
        small && styles.chipSmall,
      ]}
    >
      <View style={[styles.dot, { backgroundColor: tint }]} />
      <Text style={[styles.label, { color: tint }, small && styles.labelSmall]}>
        {confidenceLabel(level)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: space.sm,
    paddingVertical: 6,
    paddingHorizontal: space.md,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  chipSmall: { paddingVertical: 3, paddingHorizontal: space.sm, gap: 5 },
  dot: { width: 7, height: 7, borderRadius: radius.pill },
  label: { ...type.caption, textTransform: 'uppercase' },
  labelSmall: { fontSize: 10 },
});
