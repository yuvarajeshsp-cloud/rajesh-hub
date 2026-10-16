import { useCallback, useEffect, useRef, useState } from 'react';
import type { Snapshots } from './snapshots';
import type { Store } from './store';

/**
 * Loads a store and writes every change back (from Microgreentracker's useAppData).
 * `update` always derives from the latest state, so quick successive changes can't
 * overwrite each other.
 */
export function useStore<T>(store: Store<T>): { data: T | null; error: unknown; update: (fn: (prev: T) => T) => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    store.load().then(setData, setError);
  }, [store]);

  const update = useCallback(
    (fn: (prev: T) => T) => {
      setData(prev => {
        if (prev === null) return prev;
        const next = fn(prev);
        store.save(next).catch(setError);
        return next;
      });
    },
    [store],
  );

  return { data, error, update };
}

/** Takes an on-device snapshot the first time the app is opened each day (local time). */
export function useDailySnapshot<T>(snapshots: Snapshots<T>, data: T | null): { lastBackup: string | null; snapshotNow: () => Promise<void> } {
  const [lastBackup, setLastBackup] = useState<string | null>(null);
  const checkedRef = useRef(false);

  const snapshotNow = useCallback(async () => {
    if (data === null) return;
    const at = new Date();
    await snapshots.create(data, at);
    setLastBackup(at.toISOString());
  }, [snapshots, data]);

  useEffect(() => {
    if (checkedRef.current || data === null) return;
    checkedRef.current = true;
    snapshots
      .list()
      .then(list => {
        const latest = list[0]?.timestamp;
        if (latest && new Date(latest).toDateString() === new Date().toDateString()) setLastBackup(latest);
        else return snapshotNow();
      })
      .catch(e => console.error('Daily snapshot failed:', e));
  }, [snapshots, data, snapshotNow]);

  return { lastBackup, snapshotNow };
}
