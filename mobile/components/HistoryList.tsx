import { useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, space, type } from '../lib/theme';
import type { HistoryEntry } from '../lib/types';
import { ConfidenceChip } from './ConfidenceChip';
import { Sprig } from './Sprig';

/** Show relative dates for saved identifications. */
function timeAgo(at: number): string {
  const mins = Math.floor((Date.now() - at) / 60_000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;

  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;

  return new Date(at).toLocaleDateString();
}

export function HistoryList({
  entries,
  onOpen,
}: {
  entries: HistoryEntry[];
  onOpen: (entry: HistoryEntry) => void;
}) {
  if (entries.length === 0) {
    return (
      <View style={styles.empty}>
        <Sprig size={92} color={colors.accent} opacity={0.22} />
        <Text style={styles.emptyTitle}>Nothing identified yet</Text>
        <Text style={styles.emptyText}>
          Plants you identify are saved here — on this device only, never uploaded.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.list}>
      {entries.map((entry) => (
        <HistoryRow key={entry.id} entry={entry} onPress={() => onOpen(entry)} />
      ))}
    </View>
  );
}

function HistoryRow({ entry, onPress }: { entry: HistoryEntry; onPress: () => void }) {
  // Use a placeholder if a cached photo is missing; keep the saved result accessible.
  const [thumbFailed, setThumbFailed] = useState(false);

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
    >
      {thumbFailed ? (
        <View style={[styles.thumb, styles.thumbMissing]}>
          <Text style={styles.thumbMissingIcon}>❧</Text>
        </View>
      ) : (
        <Image
          source={{ uri: entry.uri }}
          style={styles.thumb}
          onError={() => setThumbFailed(true)}
        />
      )}

      <View style={styles.rowText}>
        <Text style={styles.name} numberOfLines={1}>
          {entry.common_name}
        </Text>
        <Text style={styles.latin} numberOfLines={1}>
          {entry.scientific_name}
        </Text>
      </View>

      <View style={styles.rowMeta}>
        <ConfidenceChip level={entry.confidence} small />
        <Text style={styles.when}>{timeAgo(entry.at)}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  list: { gap: space.sm },

  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    padding: space.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowPressed: { opacity: 0.6 },

  thumb: {
    width: 52,
    height: 52,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
  },
  thumbMissing: { alignItems: 'center', justifyContent: 'center' },
  thumbMissingIcon: { fontSize: 20, color: colors.accentDim },

  rowText: { flex: 1, gap: 2 },
  name: { ...type.bodyStrong, color: colors.text },
  latin: { ...type.mono, fontSize: 13, color: colors.textMuted },

  rowMeta: { alignItems: 'flex-end', gap: space.xs },
  when: { ...type.small, fontSize: 11, color: colors.textFaint },

  // Placeholder for an empty history list.
  empty: {
    alignItems: 'center',
    gap: space.sm,
    paddingVertical: space.xl,
    paddingHorizontal: space.xl,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: colors.border,
    backgroundColor: colors.surfaceAlt,
  },
  emptyTitle: { ...type.bodyStrong, color: colors.textMuted, marginTop: space.xs },
  emptyText: {
    ...type.small,
    color: colors.textFaint,
    textAlign: 'center',
    lineHeight: 19,
  },
});
