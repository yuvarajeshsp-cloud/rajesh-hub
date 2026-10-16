import { Directory, Encoding, Filesystem, type FileInfo } from '@capacitor/filesystem';

// Everything the app stores lives under one folder in the app's private storage:
// Android internal files, iOS Documents (included in the iCloud device backup),
// and IndexedDB when running in a browser.
export const DIRECTORY = Directory.Data;
let root = 'app';
/** Call once at startup, before any read or write: configureStorage({ root: 'thulir' }). */
export const configureStorage = (opts: { root: string }) => { root = opts.root; };
export const getRoot = () => root;

export const readText = async (path: string): Promise<string | null> => {
  try {
    const { data } = await Filesystem.readFile({ path, directory: DIRECTORY, encoding: Encoding.UTF8 });
    return typeof data === 'string' ? data : await data.text();
  } catch {
    return null; // missing file
  }
};

export const writeText = async (path: string, text: string): Promise<void> => {
  await Filesystem.writeFile({ path, data: text, directory: DIRECTORY, encoding: Encoding.UTF8, recursive: true });
};

export const readBase64 = async (path: string): Promise<string> => {
  const { data } = await Filesystem.readFile({ path, directory: DIRECTORY });
  if (typeof data !== 'string') throw new Error(`Unexpected binary read for ${path}`);
  return data;
};

export const writeBase64 = async (path: string, base64: string): Promise<void> => {
  await Filesystem.writeFile({ path, data: base64, directory: DIRECTORY, recursive: true });
};

export const listFiles = async (path: string): Promise<FileInfo[]> => {
  try {
    const { files } = await Filesystem.readdir({ path, directory: DIRECTORY });
    return files.filter(f => f.type === 'file');
  } catch {
    return []; // folder not created yet
  }
};

export const deleteFile = async (path: string): Promise<void> => {
  await Filesystem.deleteFile({ path, directory: DIRECTORY });
};

export { bytesToBase64, base64ToBytes } from '@rajesh-hub/native';
