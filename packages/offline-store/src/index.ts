export { configureStorage, getRoot, readText, writeText, readBase64, writeBase64, listFiles, deleteFile, bytesToBase64, base64ToBytes } from './fs';
export { createStore, type Store, type StoreOptions } from './store';
export { createSnapshots, type Snapshots, type SnapshotInfo } from './snapshots';
export { createBackup, type BackupOptions, type ParsedBackup } from './backup';
export { savePhotoFromFile, savePhotoBase64, readPhotoBase64, photoSrc, sharePhoto, deleteUnusedPhotos, isSafePhotoName, type PhotoSize } from './photos';
export { useStore, useDailySnapshot } from './react';
