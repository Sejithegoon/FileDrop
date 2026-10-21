// Which files have previews, remembered for this session (shared by the thumbnails and the upload queue).
export const noPreview = new Set<string>(); // "serverId:itemId:modified" known to have no preview
export const previewFiles = new Map<string, string>(); // same key -> cached file uri

/** Forget "no preview" answers, e.g. after the phone just sent one. */
export function retryThumbs() {
  noPreview.clear();
}
