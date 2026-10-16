import { strFromU8, strToU8, unzipSync, zipSync, type Zippable } from 'fflate';
import { saveFile } from '@rajesh-hub/native';
import { base64ToBytes, bytesToBase64 } from './fs';
import { isSafePhotoName, readPhotoBase64, savePhotoBase64 } from './photos';

// A backup file is a .zip holding backup.json (all records) and photos/<name> for every photo
// (from Microgreentracker). Restoring is two steps: parse (changes nothing), then the app
// writes the photos and replaces its data, so the user can confirm in between.

const MANIFEST = 'backup.json';

export interface BackupOptions<T> {
  /** Identifies your app's backups, e.g. "thulir-microgreen-backup". Files with another format are rejected. */
  format: string;
  schemaVersion: number;
  /** Shown in error messages: "This file is not a <appName> backup." */
  appName: string;
  /** Download name stem; the local date and .zip are appended. */
  filePrefix: string;
  /** Photo file names referenced by the data; return [] if the app has no photos. */
  photoNames: (data: T) => string[];
  normalize?: (raw: unknown) => T;
}

export interface ParsedBackup<T> {
  data: T;
  photos: Record<string, string>; // name → base64
  createdAt?: string;
}

const localDateStamp = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

export function createBackup<T>(opts: BackupOptions<T>) {
  const normalize = opts.normalize ?? ((raw: unknown) => raw as T);
  const notOurs = () => new Error(`This file is not a ${opts.appName} backup.`);

  const exportFile = async (data: T): Promise<void> => {
    const manifest = { format: opts.format, schemaVersion: opts.schemaVersion, createdAt: new Date().toISOString(), data };
    const files: Zippable = { [MANIFEST]: strToU8(JSON.stringify(manifest)) };
    for (const name of new Set(opts.photoNames(data))) {
      try {
        files[`photos/${name}`] = [base64ToBytes(await readPhotoBase64(name)), { level: 0 }]; // already compressed
      } catch {
        // photo file missing on this device; the record is still backed up
      }
    }
    await saveFile(`${opts.filePrefix}-${localDateStamp()}.zip`, zipSync(files), 'application/zip');
  };

  const parseFile = async (file: File): Promise<ParsedBackup<T>> => {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let entries: Record<string, Uint8Array>;
    try {
      entries = unzipSync(bytes);
    } catch {
      throw notOurs();
    }
    const manifestBytes = entries[MANIFEST];
    if (!manifestBytes) throw notOurs();
    const manifest = JSON.parse(strFromU8(manifestBytes));
    if (manifest.format !== opts.format || !manifest.data) throw notOurs();
    if (manifest.schemaVersion > opts.schemaVersion) {
      throw new Error('This backup was made by a newer version of the app. Please update the app first.');
    }
    const photos: Record<string, string> = {};
    for (const [path, content] of Object.entries(entries)) {
      const name = path.startsWith('photos/') ? path.slice('photos/'.length) : '';
      if (isSafePhotoName(name)) photos[name] = bytesToBase64(content);
    }
    return { data: normalize(manifest.data), photos, createdAt: manifest.createdAt };
  };

  /** Writes the backup's photos; the caller then replaces the app data with `backup.data`. */
  const writePhotos = async (backup: ParsedBackup<T>): Promise<void> => {
    for (const [name, base64] of Object.entries(backup.photos)) await savePhotoBase64(name, base64);
  };

  return { exportFile, parseFile, writePhotos };
}
