const ALLOWED_PHOTO_HOSTS = new Set(["lh3.googleusercontent.com"]);

/** @param {string} raw */
export function allowedPhotoSource(raw) {
  try {
    const url = new URL(raw);
    return url.protocol === "https:" && ALLOWED_PHOTO_HOSTS.has(url.hostname) ? url : null;
  } catch {
    return null;
  }
}
