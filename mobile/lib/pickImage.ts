import * as ImagePicker from 'expo-image-picker';

/** Shared photo-library picker. Returns the image or null on cancellation. */
export async function pickFromLibrary(): Promise<string | null> {
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: 'images',
    quality: 0.9,
  });
  if (result.canceled) return null;
  return result.assets[0]?.uri ?? null;
}
