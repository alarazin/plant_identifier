import { useEffect, useRef } from 'react';
import { Animated, Easing, Image, StyleSheet, Text, View } from 'react-native';

import { Button } from '../components/Button';
import type { Stage } from '../lib/api';
import { colors, space, type } from '../lib/theme';

const COPY: Record<Stage, string> = {
  preparing: 'Preparing photo',
  identifying: 'Identifying',
};

export function AnalyzingScreen({
  uri,
  stage,
  onCancel,
}: {
  uri: string;
  stage: Stage;
  onCancel: () => void;
}) {
  const sweep = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(sweep, {
        toValue: 1,
        duration: 1600,
        easing: Easing.inOut(Easing.quad),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [sweep]);

  const translateY = sweep.interpolate({
    inputRange: [0, 1],
    outputRange: ['-50%', '50%'],
  });

  return (
    <View style={styles.container}>
      <View style={styles.imageWrap}>
        <Image source={{ uri }} style={styles.image} resizeMode="cover" />
        <View style={styles.scrim} />
        <Animated.View style={[styles.sweep, { transform: [{ translateY }] }]} />
      </View>

      <View style={styles.status}>
        <Text style={styles.stage}>{COPY[stage]}</Text>
        <Text style={styles.detail}>
          {stage === 'preparing'
            ? 'Resizing so only what the model needs is sent'
            : 'Comparing leaf shape, margin and habit'}
        </Text>
      </View>

      <Button label="Cancel" variant="ghost" onPress={onCancel} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.xl,
    padding: space.xl,
  },
  imageWrap: {
    width: '100%',
    aspectRatio: 1,
    maxHeight: 360,
    borderRadius: 20,
    overflow: 'hidden',
  },
  image: { width: '100%', height: '100%' },
  scrim: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.veil,
  },
  // Progress line over the photo.
  sweep: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 2,
    top: '50%',
    backgroundColor: colors.accent,
    opacity: 0.35,
  },
  status: { alignItems: 'center', gap: space.xs },
  stage: { ...type.title, color: colors.text },
  detail: { ...type.small, color: colors.textFaint, textAlign: 'center' },
});
