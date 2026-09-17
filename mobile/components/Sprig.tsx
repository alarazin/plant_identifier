import { StyleSheet, View, type ViewStyle } from 'react-native';

import { colors } from '../lib/theme';

/** Plant mark built from Views on a 100×100 grid, scaled by size. */
export function Sprig({
  size = 120,
  color = colors.accentDim,
  opacity = 1,
  style,
}: {
  size?: number;
  color?: string;
  opacity?: number;
  style?: ViewStyle;
}) {
  const u = size / 100;

  // Leaf pairs become smaller toward the tip.
  const pairs = [
    { y: 80, len: 36, wid: 10, angle: 38 },
    { y: 63, len: 32, wid: 9, angle: 36 },
    { y: 47, len: 26, wid: 8, angle: 33 },
    { y: 33, len: 19, wid: 7, angle: 30 },
    { y: 22, len: 13, wid: 6, angle: 27 },
  ];

  // Overlap the stem to keep rotated leaves attached.
  const bite = 4;

  return (
    <View style={[{ width: size, height: size, opacity, pointerEvents: 'none' }, style]}>
      {/* Stem */}
      <View
        style={{
          position: 'absolute',
          left: 49.2 * u,
          top: 17 * u,
          width: 1.6 * u,
          height: 79 * u,
          borderRadius: u,
          backgroundColor: color,
        }}
      />

      {pairs.map((p, i) => (
        <View key={i}>
          <Leaf
            u={u}
            x={50 - p.len + bite}
            y={p.y - p.wid / 2}
            len={p.len}
            wid={p.wid}
            angle={p.angle}
            color={color}
          />
          <Leaf
            u={u}
            x={50 - bite}
            y={p.y - p.wid / 2}
            len={p.len}
            wid={p.wid}
            angle={-p.angle}
            color={color}
            flip
          />
        </View>
      ))}
    </View>
  );
}

function Leaf({
  u,
  x,
  y,
  len,
  wid,
  angle,
  color,
  flip,
}: {
  u: number;
  x: number;
  y: number;
  len: number;
  wid: number;
  angle: number;
  color: string;
  flip?: boolean;
}) {
  // Round opposite corners to form each leaf.
  const r = Math.min(len, wid) * u;
  const rounded: ViewStyle = flip
    ? { borderTopRightRadius: r, borderBottomLeftRadius: r }
    : { borderTopLeftRadius: r, borderBottomRightRadius: r };

  return (
    <View
      style={[
        styles.leaf,
        rounded,
        {
          left: x * u,
          top: y * u,
          width: len * u,
          height: wid * u,
          backgroundColor: color,
          transform: [{ rotate: `${angle}deg` }],
        },
      ]}
    />
  );
}

const styles = StyleSheet.create({
  leaf: { position: 'absolute' },
});
