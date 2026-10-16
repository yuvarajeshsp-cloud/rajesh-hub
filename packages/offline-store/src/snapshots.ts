import { deleteFile, getRoot, listFiles, readText, writeText } from './fs';

// On-device snapshots of a store's data (from Microgreentracker). Photos are shared
// files referenced by name, so a snapshot is only the JSON records.

export interface SnapshotInfo {
  id: string;
  timestamp: string;
  label: string;
  size: number;
}

export interface Snapshots<T> {
  list: () => Promise<SnapshotInfo[]>;
  create: (data: T, at?: Date) => Promise<void>;
  read: (id: string) => Promise<T>;
  remove: (id: string) => Promise<void>;
  /** Every value `collect` returns across all kept snapshots, e.g. photo names still referenced. */
  collect: <V>(fn: (data: T) => V[]) => Promise<V[]>;
}

export function createSnapshots<T>(opts: { normalize?: (raw: unknown) => T; max?: number; folder?: string } = {}): Snapshots<T> {
  const max = opts.max ?? 30;
  const normalize = opts.normalize ?? ((raw: unknown) => raw as T);
  const dir = () => `${getRoot()}/${opts.folder ?? 'snapshots'}`;
  const pathOf = (id: string) => `${dir()}/${id}.json`;

  const list = async (): Promise<SnapshotInfo[]> =>
    (await listFiles(dir()))
      .map(f => ({ match: /^snapshot-(\d+)\.json$/.exec(f.name), size: f.size }))
      .filter(f => f.match)
      .map(({ match, size }) => {
        const date = new Date(Number(match![1]));
        return { id: `snapshot-${match![1]}`, timestamp: date.toISOString(), label: date.toLocaleString(), size };
      })
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp));

  const create = async (data: T, at: Date = new Date()): Promise<void> => {
    await writeText(pathOf(`snapshot-${at.getTime()}`), JSON.stringify({ timestamp: at.toISOString(), data }));
    const all = await list();
    await Promise.all(all.slice(max).map(s => deleteFile(pathOf(s.id)).catch(() => {})));
  };

  const read = async (id: string): Promise<T> => {
    const text = await readText(pathOf(id));
    if (!text) throw new Error('Snapshot not found');
    return normalize(JSON.parse(text).data ?? {});
  };

  const remove = (id: string): Promise<void> => deleteFile(pathOf(id));

  const collect = async <V,>(fn: (data: T) => V[]): Promise<V[]> => {
    const out: V[] = [];
    for (const s of await list()) {
      try {
        out.push(...fn(await read(s.id)));
      } catch {
        // unreadable snapshot; ignore
      }
    }
    return out;
  };

  return { list, create, read, remove, collect };
}
