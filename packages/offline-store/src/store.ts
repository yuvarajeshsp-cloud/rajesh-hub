import { getRoot, readText, writeText } from './fs';

// Crash-safe local data store (from Microgreentracker).
//
// The data is written alternately to two files, each stamped with an increasing sequence
// number. If the app is killed mid-write only the file being written is damaged, and the
// loader falls back to the other one, so a crash can never lose more than the last change.
// Saves are queued and coalesced: only the newest data is written once the current write finishes.

export interface StoreOptions<T> {
  /** Bump when the shape of T changes; `normalize` must accept older shapes. */
  schemaVersion: number;
  /** Data for a first launch. */
  defaults: () => T;
  /** Fill in missing fields and upgrade old shapes. Runs on every load. */
  normalize?: (raw: unknown) => T;
  /** Runs once when no data file exists yet, e.g. to move data from localStorage. Return null if there is nothing to migrate. */
  migrate?: () => Promise<T | null>;
  /** File name stem; two stores in one app need different names. Default "data". */
  name?: string;
}

interface Envelope<T> {
  schemaVersion: number;
  seq: number;
  savedAt: string;
  data: T;
}

export interface Store<T> {
  load: () => Promise<T>;
  save: (data: T) => Promise<void>;
  schemaVersion: number;
  normalize: (raw: unknown) => T;
}

export function createStore<T>(opts: StoreOptions<T>): Store<T> {
  const name = opts.name ?? 'data';
  const normalize = opts.normalize ?? ((raw: unknown) => raw as T);
  const slots = () => [`${getRoot()}/${name}-a.json`, `${getRoot()}/${name}-b.json`];

  let seq = 0;
  let pending: T | null = null;
  let writing: Promise<void> | null = null;
  let loading: Promise<T> | null = null;

  const readSlot = async (path: string): Promise<Envelope<T> | null> => {
    const text = await readText(path);
    if (!text) return null;
    try {
      const env = JSON.parse(text) as Envelope<T>;
      return typeof env.seq === 'number' && env.data ? env : null;
    } catch {
      return null; // partially written
    }
  };

  const flush = async (): Promise<void> => {
    while (pending) {
      const data = pending;
      pending = null;
      const next = seq + 1;
      const env: Envelope<T> = { schemaVersion: opts.schemaVersion, seq: next, savedAt: new Date().toISOString(), data };
      try {
        await writeText(slots()[next % 2], JSON.stringify(env));
      } catch (e) {
        // Keep the unsaved data queued so the next change retries it, and leave seq alone so
        // the retry goes to the same file instead of overwriting the last good copy.
        pending = pending ?? data;
        throw e;
      }
      seq = next;
    }
  };

  const save = (data: T): Promise<void> => {
    pending = data;
    if (!writing) writing = flush().finally(() => { writing = null; });
    return writing;
  };

  const doLoad = async (): Promise<T> => {
    const found = (await Promise.all(slots().map(readSlot))).filter((e): e is Envelope<T> => e !== null);
    if (found.length > 0) {
      const latest = found.reduce((a, b) => (b.seq > a.seq ? b : a));
      seq = latest.seq;
      return normalize(latest.data);
    }
    const migrated = opts.migrate ? await opts.migrate() : null;
    const fresh = migrated ?? opts.defaults();
    await save(fresh);
    return fresh;
  };

  const load = (): Promise<T> => {
    loading = loading ?? doLoad();
    return loading;
  };

  return { load, save, schemaVersion: opts.schemaVersion, normalize };
}
