import { CameraView, useCameraPermissions } from 'expo-camera';
import { useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button } from '../components/Button';
import { pickFromLibrary } from '../lib/pickImage';
import { colors, radius, space, type } from '../lib/theme';

/** Camera view with framing tips. */
export function CameraScreen({
  onCapture,
  onClose,
}: {
  onCapture: (uri: string) => void;
  onClose: () => void;
}) {
  const [permission, requestPermission] = useCameraPermissions();
  const [busy, setBusy] = useState(false);
  const cameraRef = useRef<CameraView>(null);

  const takePhoto = async () => {
    if (!cameraRef.current || busy) return;
    setBusy(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.9 });
      if (photo?.uri) onCapture(photo.uri);
    } finally {
      setBusy(false);
    }
  };

  const chooseFromLibrary = async () => {
    const uri = await pickFromLibrary();
    if (uri) onCapture(uri);
  };

  if (!permission) {
    return <View style={styles.container} />;
  }

  if (!permission.granted) {
    return (
      <View style={[styles.container, styles.permission]}>
        <Text style={styles.permissionIcon}>❧</Text>
        <Text style={styles.permissionTitle}>Camera access needed</Text>
        <Text style={styles.permissionBody}>
          Point the camera at a leaf or flower to identify it. Photos are sent to
          the identification service and are not stored.
        </Text>
        <Button label="Allow camera" onPress={requestPermission} />
        <Button label="Choose from library instead" variant="ghost" onPress={chooseFromLibrary} />
        <Button label="Back" variant="ghost" onPress={onClose} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="back" />

      <View style={styles.overlay} pointerEvents="box-none">
        <View style={styles.header}>
          <Pressable
            onPress={onClose}
            hitSlop={space.md}
            style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}
          >
            <Text style={styles.backIcon}>‹</Text>
          </Pressable>
          <View>
            <Text style={styles.brand}>PlantKey</Text>
            <Text style={styles.brandSub}>Plant identification</Text>
          </View>
        </View>

        <View style={styles.reticle} pointerEvents="none">
          <View style={[styles.corner, styles.tl]} />
          <View style={[styles.corner, styles.tr]} />
          <View style={[styles.corner, styles.bl]} />
          <View style={[styles.corner, styles.br]} />
        </View>

        <View style={styles.footer}>
          <Text style={styles.tip}>
            Fill the frame with one leaf or flower · get close · avoid shade
          </Text>

          <View style={styles.controls}>
            <Pressable
              onPress={chooseFromLibrary}
              style={({ pressed }) => [styles.libraryButton, pressed && styles.pressed]}
            >
              <Text style={styles.libraryIcon}>▤</Text>
            </Pressable>

            <Pressable
              onPress={takePhoto}
              disabled={busy}
              style={({ pressed }) => [
                styles.shutter,
                pressed && styles.shutterPressed,
                busy && styles.shutterBusy,
              ]}
            >
              <View style={styles.shutterInner} />
            </Pressable>

            {/* Spacer keeps the shutter optically centred. */}
            <View style={styles.libraryButton} />
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  overlay: { flex: 1, justifyContent: 'space-between' },

  header: {
    paddingTop: 60,
    paddingHorizontal: space.xl,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
  },
  backButton: {
    width: 36,
    height: 36,
    borderRadius: radius.pill,
    backgroundColor: colors.scrim,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Nudged up: the chevron glyph sits low in its line box.
  backIcon: { color: colors.onImage, fontSize: 28, lineHeight: 30, marginTop: -4 },
  brand: { ...type.title, color: colors.onImage },
  brandSub: { ...type.caption, color: colors.onImageAccent, textTransform: 'uppercase' },

  reticle: {
    alignSelf: 'center',
    width: '72%',
    aspectRatio: 1,
    maxHeight: 320,
  },
  corner: {
    position: 'absolute',
    width: 26,
    height: 26,
    borderColor: 'rgba(251,248,242,0.55)',
  },
  tl: { top: 0, left: 0, borderTopWidth: 2, borderLeftWidth: 2, borderTopLeftRadius: 6 },
  tr: { top: 0, right: 0, borderTopWidth: 2, borderRightWidth: 2, borderTopRightRadius: 6 },
  bl: { bottom: 0, left: 0, borderBottomWidth: 2, borderLeftWidth: 2, borderBottomLeftRadius: 6 },
  br: { bottom: 0, right: 0, borderBottomWidth: 2, borderRightWidth: 2, borderBottomRightRadius: 6 },

  footer: { paddingBottom: 44, gap: space.lg },
  tip: {
    ...type.small,
    color: 'rgba(251,248,242,0.9)',
    textAlign: 'center',
    paddingHorizontal: space.xl,
  },
  controls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: space.xxl,
  },
  shutter: {
    width: 76,
    height: 76,
    borderRadius: radius.pill,
    borderWidth: 3,
    borderColor: colors.onImage,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shutterPressed: { transform: [{ scale: 0.94 }] },
  shutterBusy: { opacity: 0.5 },
  shutterInner: {
    width: 58,
    height: 58,
    borderRadius: radius.pill,
    backgroundColor: colors.onImage,
  },
  libraryButton: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.scrim,
    alignItems: 'center',
    justifyContent: 'center',
  },
  libraryIcon: { color: colors.onImage, fontSize: 20 },
  pressed: { opacity: 0.6 },

  permission: {
    justifyContent: 'center',
    alignItems: 'center',
    padding: space.xl,
    gap: space.lg,
  },
  permissionIcon: { fontSize: 44, color: colors.accentDim },
  permissionTitle: { ...type.title, color: colors.text },
  permissionBody: {
    ...type.body,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 22,
  },
});
