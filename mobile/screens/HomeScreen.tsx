import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { HistoryList } from '../components/HistoryList';
import { Sprig } from '../components/Sprig';
import { colors, radius, space, type } from '../lib/theme';
import type { HistoryEntry } from '../lib/types';

/** Home screen with camera and photo-library options. */
export function HomeScreen({
  history,
  onTakePhoto,
  onUpload,
  onOpenEntry,
  onClearHistory,
}: {
  history: HistoryEntry[];
  onTakePhoto: () => void;
  onUpload: () => void;
  onOpenEntry: (entry: HistoryEntry) => void;
  onClearHistory: () => void;
}) {
  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.hero}>
        {/* Decorative plant mark, clipped to the panel. */}
        <Sprig size={260} color={colors.accent} opacity={0.14} style={styles.heroSprig} />

        <Text style={styles.brandSub}>PLANT IDENTIFICATION</Text>
        <Text style={styles.brand}>PlantKey</Text>
        <Text style={styles.lede}>
          Photograph a leaf or flower to get a ranked identification with care notes.
        </Text>
      </View>

      <View style={styles.actions}>
        <ActionTile
          glyph="◎"
          label="Take a photo"
          hint="Use the camera"
          primary
          onPress={onTakePhoto}
        />
        <ActionTile glyph="▤" label="Upload" hint="From your library" onPress={onUpload} />
      </View>

      <View style={styles.historyHeader}>
        <View style={styles.historyTitleRow}>
          <Text style={styles.sectionTitle}>RECENT</Text>
          {history.length > 0 && (
            <View style={styles.countPill}>
              <Text style={styles.countText}>{history.length}</Text>
            </View>
          )}
        </View>

        {history.length > 0 && (
          <Pressable
            onPress={onClearHistory}
            hitSlop={space.md}
            style={({ pressed }) => pressed && styles.pressed}
          >
            <Text style={styles.clear}>Clear</Text>
          </Pressable>
        )}
      </View>

      <HistoryList entries={history} onOpen={onOpenEntry} />
    </ScrollView>
  );
}

function ActionTile({
  glyph,
  label,
  hint,
  primary,
  onPress,
}: {
  glyph: string;
  label: string;
  hint: string;
  primary?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.tile,
        primary ? styles.tilePrimary : styles.tileSecondary,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.tileGlyph, primary ? styles.onPrimary : styles.onSecondary]}>
        {glyph}
      </Text>
      <View style={styles.tileText}>
        <Text style={[styles.tileLabel, primary ? styles.onPrimary : styles.tileLabelAlt]}>
          {label}
        </Text>
        <Text style={[styles.tileHint, primary ? styles.onPrimaryFaint : styles.onSecondary]}>
          {hint}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: {
    padding: space.lg,
    paddingTop: space.lg,
    paddingBottom: space.xxl,
    gap: space.lg,
  },

  hero: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space.xl,
    paddingRight: space.xxl * 2.6,
    gap: space.xs,
    overflow: 'hidden',
  },
  heroSprig: { position: 'absolute', right: -54, top: -26 },
  brandSub: { ...type.caption, color: colors.accent },
  brand: { ...type.display, fontSize: 32, color: colors.text },
  lede: {
    ...type.body,
    color: colors.textMuted,
    lineHeight: 22,
    marginTop: space.xs,
  },

  actions: { flexDirection: 'row', gap: space.md },
  tile: {
    flex: 1,
    borderRadius: radius.lg,
    padding: space.lg,
    gap: space.xl,
    minHeight: 132,
    justifyContent: 'space-between',
  },
  tilePrimary: { backgroundColor: colors.accent },
  tileSecondary: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tileGlyph: { fontSize: 26 },
  tileText: { gap: 2 },
  tileLabel: { ...type.bodyStrong },
  tileLabelAlt: { color: colors.text },
  tileHint: { ...type.small, fontSize: 12 },
  onPrimary: { color: colors.bg },
  onPrimaryFaint: { color: colors.bg, opacity: 0.75 },
  onSecondary: { color: colors.textFaint },

  historyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: space.sm,
  },
  historyTitleRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  sectionTitle: { ...type.caption, color: colors.textFaint },
  countPill: {
    minWidth: 20,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
  },
  countText: { ...type.caption, fontSize: 10, color: colors.textMuted },
  clear: { ...type.caption, color: colors.textMuted },
  pressed: { opacity: 0.6 },
});
