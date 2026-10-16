import { Capacitor } from '@capacitor/core';
import { Filesystem } from '@capacitor/filesystem';
import { saveFile } from '@rajesh-hub/native';
import { DIRECTORY, getRoot, base64ToBytes, bytesToBase64, deleteFile, listFiles, readBase64, writeBase64 } from './fs';

// Photos live in <root>/photos, thumbnails in <root>/thumbs (from Microgreentracker).
const photosDir = () => `${getRoot()}/photos`;
// Small copies for grids and strips, so a screen of photos doesn't decode dozens of full-size images.
// They are never backed up; missing ones are recreated from the full photo when first shown.
const thumbsDir = () => `${getRoot()}/thumbs`;
const MAX_SIZE = 1600; // px, longest side
const THUMB_SIZE = 320;
const JPEG_QUALITY = 0.8;

export type PhotoSize = 'full' | 'thumb';

// Photo names come from backup files too, so only accept plain file names.
export const isSafePhotoName = (name: string): boolean => /^[A-Za-z0-9_-]+\.(jpe?g|png|webp|gif|heic)$/i.test(name);

const newPhotoName = (ext: string) =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 10)}.${ext}`;

const thumbNameFor = (name: string) => `${name.replace(/\.[^.]+$/, '')}.jpg`;

const mimeFor = (name: string) => {
  const ext = name.split('.').pop()?.toLowerCase();
  return ext === 'jpg' || ext === 'jpeg' ? 'image/jpeg' : `image/${ext}`;
};

const compressToJpeg = async (file: Blob, maxSize: number, quality = JPEG_QUALITY): Promise<Blob> => {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxSize / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve, reject) =>
    canvas.toBlob(b => (b ? resolve(b) : reject(new Error('Could not encode photo'))), 'image/jpeg', quality)
  );
};

const blobBase64 = async (blob: Blob) => bytesToBase64(new Uint8Array(await blob.arrayBuffer()));

// Shrinks a camera/gallery image and stores it as its own file. Returns the file name to keep on your record.
export const savePhotoFromFile = async (file: File): Promise<string> => {
  let blob: Blob = file;
  let ext = 'jpg';
  try {
    blob = await compressToJpeg(file, MAX_SIZE);
  } catch {
    // The WebView couldn't decode it; keep the original bytes.
    const original = file.name.split('.').pop()?.toLowerCase();
    ext = original && isSafePhotoName(`x.${original}`) ? original : 'jpg';
  }
  const name = newPhotoName(ext);
  await writeBase64(`${photosDir()}/${name}`, await blobBase64(blob));
  try {
    await writeBase64(`${thumbsDir()}/${thumbNameFor(name)}`, await blobBase64(await compressToJpeg(blob, THUMB_SIZE, 0.75)));
  } catch {
    // made on demand instead
  }
  return name;
};

export const savePhotoBase64 = async (name: string, base64: string): Promise<void> => {
  if (!isSafePhotoName(name)) throw new Error(`Invalid photo name: ${name}`);
  await writeBase64(`${photosDir()}/${name}`, base64);
};

export const readPhotoBase64 = (name: string): Promise<string> => readBase64(`${photosDir()}/${name}`);

// One thumbnail is made at a time, so opening a big gallery can't exhaust memory.
let thumbQueue: Promise<unknown> = Promise.resolve();
const ensureThumb = (name: string): Promise<string> => {
  const path = `${thumbsDir()}/${thumbNameFor(name)}`;
  const task = thumbQueue.then(async () => {
    try {
      await Filesystem.stat({ path, directory: DIRECTORY });
      return path;
    } catch {
      const full = new Blob([base64ToBytes(await readPhotoBase64(name))], { type: mimeFor(name) });
      await writeBase64(path, await blobBase64(await compressToJpeg(full, THUMB_SIZE, 0.75)));
      return path;
    }
  });
  thumbQueue = task.catch(() => {});
  return task;
};

const srcFor = async (path: string, mime: string): Promise<string> => {
  if (Capacitor.isNativePlatform()) {
    // Lets the WebView load the file directly instead of passing it through JavaScript.
    const { uri } = await Filesystem.getUri({ path, directory: DIRECTORY });
    return Capacitor.convertFileSrc(uri);
  }
  return `data:${mime};base64,${await readBase64(path)}`;
};

const srcCache = new Map<string, Promise<string>>();

// A URL an <img> can show. Rejects if the photo file is missing on this device.
export const photoSrc = (name: string, size: PhotoSize): Promise<string> => {
  const key = `${size}:${name}`;
  let src = srcCache.get(key);
  if (!src) {
    src = size === 'thumb'
      ? ensureThumb(name).then(path => srcFor(path, 'image/jpeg'))
      : srcFor(`${photosDir()}/${name}`, mimeFor(name));
    src.catch(() => srcCache.delete(key)); // allow a retry later, e.g. after a restore
    srcCache.set(key, src);
  }
  return src;
};

// Opens the share sheet for one photo (downloads it in a browser). `baseName` gets the photo's extension.
export const sharePhoto = async (name: string, baseName: string): Promise<void> => {
  const ext = name.split('.').pop();
  const safeBase = baseName.replace(/[^A-Za-z0-9_-]+/g, '-');
  await saveFile(`${safeBase}.${ext}`, base64ToBytes(await readPhotoBase64(name)), mimeFor(name));
};

// Deletes photo files (and their thumbnails) that are not in `inUse` (build it from your current
// data plus snapshots.collect(...)). Files written after `olderThan` are kept: they may belong to a change
// that isn't saved yet.
export const deleteUnusedPhotos = async (inUse: Set<string>, olderThan: number): Promise<void> => {
  const thumbsInUse = new Set([...inUse].map(thumbNameFor));
  const [photos, thumbs] = await Promise.all([listFiles(photosDir()), listFiles(thumbsDir())]);
  const unused = [
    ...photos.filter(f => !inUse.has(f.name) && f.mtime < olderThan).map(f => `${photosDir()}/${f.name}`),
    ...thumbs.filter(f => !thumbsInUse.has(f.name) && f.mtime < olderThan).map(f => `${thumbsDir()}/${f.name}`),
  ];
  await Promise.all(unused.map(path => deleteFile(path).catch(() => {})));
};
