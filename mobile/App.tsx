import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef, useState } from 'react';
import { Alert, Platform, SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button } from './components/Button';
import { identify, type Stage } from './lib/api';
import { API_BASE } from './lib/config';
import { clearHistory, loadHistory, saveIdentification } from './lib/history';
import { pickFromLibrary } from './lib/pickImage';
import { colors, space, type } from './lib/theme';
import type { HistoryEntry, IdentifyResponse } from './lib/types';
import { AnalyzingScreen } from './screens/AnalyzingScreen';
import { CameraScreen } from './screens/CameraScreen';
import { HomeScreen } from './screens/HomeScreen';
import { ResultScreen } from './screens/ResultScreen';

/** Screen state handles navigation through the home screen. */
type Screen =
  | { kind: 'home' }
  | { kind: 'camera' }
  | { kind: 'analyzing'; uri: string; stage: Stage }
  | { kind: 'result'; uri: string; result: IdentifyResponse }
  | { kind: 'error'; uri: string; message: string };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ kind: 'home' });
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const activeIdentification = useRef<AbortController | null>(null);

  useEffect(() => () => {
    activeIdentification.current?.abort();
    activeIdentification.current = null;
  }, []);

  // Load history at startup; save and clear helpers return the updated list.
  useEffect(() => {
    loadHistory().then(setHistory);
  }, []);

  const runIdentify = async (uri: string) => {
    activeIdentification.current?.abort();
    const request = new AbortController();
    activeIdentification.current = request;
    const isCurrent = () =>
      activeIdentification.current === request && !request.signal.aborted;

    setScreen({ kind: 'analyzing', uri, stage: 'preparing' });
    try {
      const result = await identify(
        uri,
        (stage) => {
          if (!isCurrent()) return;
          setScreen((prev) =>
            isCurrent() && prev.kind === 'analyzing' ? { ...prev, stage } : prev,
          );
        },
        request.signal,
      );
      // Aborting fetch is best-effort; an older promise may still settle.
      if (!isCurrent()) return;
      setScreen({ kind: 'result', uri, result });
      const updatedHistory = await saveIdentification(uri, result);
      if (isCurrent()) setHistory(updatedHistory);
    } catch (err: any) {
      if (!isCurrent()) return;
      setScreen({ kind: 'error', uri, message: err?.message ?? 'Something went wrong.' });
    } finally {
      if (activeIdentification.current === request) activeIdentification.current = null;
    }
  };

  const goHome = () => setScreen({ kind: 'home' });
  const cancelIdentification = () => {
    activeIdentification.current?.abort();
    activeIdentification.current = null;
    goHome();
  };
  const openCamera = () => setScreen({ kind: 'camera' });

  const uploadFromLibrary = async () => {
    const uri = await pickFromLibrary();
    if (uri) runIdentify(uri);
  };

  // Open the saved response in the result screen.
  const openEntry = (entry: HistoryEntry) =>
    setScreen({ kind: 'result', uri: entry.uri, result: entry.result });

  const confirmClearHistory = () => {
    const wipe = async () => {
      await clearHistory();
      setHistory([]);
    };

    // Use browser confirmation because Alert.alert is not implemented on web.
    if (Platform.OS === 'web') {
      if (window.confirm('Clear every saved identification on this device?')) wipe();
      return;
    }

    Alert.alert('Clear history?', 'This removes every saved identification on this device.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear', style: 'destructive', onPress: wipe },
    ]);
  };

  // The viewfinder is full-bleed; every other screen respects the safe area.
  const Frame = screen.kind === 'camera' ? View : SafeAreaView;

  return (
    <Frame style={styles.root}>
      <StatusBar style="dark" />

      {screen.kind === 'home' && (
        <HomeScreen
          history={history}
          onTakePhoto={openCamera}
          onUpload={uploadFromLibrary}
          onOpenEntry={openEntry}
          onClearHistory={confirmClearHistory}
        />
      )}

      {screen.kind === 'camera' && (
        <CameraScreen onCapture={runIdentify} onClose={goHome} />
      )}

      {screen.kind === 'analyzing' && (
        <AnalyzingScreen uri={screen.uri} stage={screen.stage} onCancel={cancelIdentification} />
      )}

      {screen.kind === 'result' && (
        <ResultScreen
          uri={screen.uri}
          result={screen.result}
          onNewPhoto={openCamera}
          onBack={goHome}
        />
      )}

      {screen.kind === 'error' && (
        <ScrollView contentContainerStyle={styles.errorWrap}>
          <Text style={styles.errorIcon}>⚠</Text>
          <Text style={styles.errorTitle}>Couldn&apos;t identify that</Text>
          <Text style={styles.errorBody}>{screen.message}</Text>
          <Text style={styles.errorHint}>Backend: {API_BASE}</Text>
          <Button label="Try again" onPress={() => runIdentify(screen.uri)} />
          <Button label="Take a new photo" variant="secondary" onPress={openCamera} />
          <Button label="Back to home" variant="ghost" onPress={goHome} />
        </ScrollView>
      )}
    </Frame>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  errorWrap: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.lg,
    padding: space.xl,
  },
  errorIcon: { fontSize: 36, color: colors.warn },
  errorTitle: { ...type.title, color: colors.text, textAlign: 'center' },
  errorBody: {
    ...type.body,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 22,
  },
  errorHint: { ...type.caption, color: colors.textFaint },
});
