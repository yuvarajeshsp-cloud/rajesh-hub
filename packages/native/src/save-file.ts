import { Capacitor } from '@capacitor/core';
import { Directory, Encoding, Filesystem } from '@capacitor/filesystem';
import { Share } from '@capacitor/share';

// Written in pieces so a large backup never has to exist as one huge base64 string.
// A multiple of 3 bytes keeps each piece valid base64 on its own.
const CHUNK_BYTES = 3 * 1024 * 1024;

export const bytesToBase64 = (bytes: Uint8Array): string => {
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  return btoa(binary);
};

export const base64ToBytes = (base64: string): Uint8Array<ArrayBuffer> => {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
};

const blobToBase64 = (blob: Blob): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(',')[1]);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });

const writeBytes = async (path: string, bytes: Uint8Array): Promise<string> => {
  let uri = '';
  for (let offset = 0; offset === 0 || offset < bytes.length; offset += CHUNK_BYTES) {
    const data = bytesToBase64(bytes.subarray(offset, offset + CHUNK_BYTES));
    if (offset === 0) ({ uri } = await Filesystem.writeFile({ path, data, directory: Directory.Cache }));
    else await Filesystem.appendFile({ path, data, directory: Directory.Cache });
  }
  return uri;
};

// Browsers download via an <a download> link, but that does nothing inside the
// Android/iOS app. There we write the file to the app cache and open the system
// share sheet so the user can save it to Google Drive, Files, email it, etc.
export const saveFile = async (filename: string, content: string | Blob | Uint8Array, mimeType: string): Promise<void> => {
  if (!Capacitor.isNativePlatform()) {
    const blob = content instanceof Blob ? content : new Blob([content as BlobPart], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    return;
  }

  let uri: string;
  if (typeof content === 'string') {
    ({ uri } = await Filesystem.writeFile({ path: filename, data: content, directory: Directory.Cache, encoding: Encoding.UTF8 }));
  } else if (content instanceof Uint8Array) {
    uri = await writeBytes(filename, content);
  } else {
    ({ uri } = await Filesystem.writeFile({ path: filename, data: await blobToBase64(content), directory: Directory.Cache }));
  }

  try {
    await Share.share({ title: filename, files: [uri] });
  } catch (e) {
    // Closing the share sheet without picking a target rejects; that's not an error.
    if (!String(e).toLowerCase().includes('cancel')) throw e;
  }
};
