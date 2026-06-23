/**
 * image-pairs.ts
 *
 * Discovers front+back image pairs from a directory.
 *
 * Strategy (in priority order):
 *   1. Read pairs.json manifest from the directory when present.
 *      Use this for doctored folders where front and back carry intentionally
 *      different product names (e.g. "cocoa_pups_front" + "coco_pops_left").
 *   2. Auto-discovery: match files that share the same base prefix before the
 *      view suffix (_front / _back / _left).
 */

import * as fs   from 'fs';
import * as path from 'path';

export interface ImagePair {
  name:  string;
  front: string;  // absolute path
  back:  string;  // absolute path
}

interface ManifestEntry {
  name:  string;
  front: string;
  back:  string;
}

const IMAGE_EXTS   = /\.(jpg|jpeg|png|JPG|JPEG|PNG)$/;
const FRONT_VIEWS  = ['_front'];
const BACK_VIEWS   = ['_back', '_left'];

function stripViewSuffix(filename: string): { key: string; isFront: boolean } | null {
  const base = filename.replace(IMAGE_EXTS, '');
  for (const suf of FRONT_VIEWS) {
    if (base.endsWith(suf)) return { key: base.slice(0, -suf.length), isFront: true };
  }
  for (const suf of BACK_VIEWS) {
    if (base.endsWith(suf)) return { key: base.slice(0, -suf.length), isFront: false };
  }
  return null;
}

export function discoverPairs(dir: string): ImagePair[] {
  if (!fs.existsSync(dir)) {
    throw new Error(`Image directory not found: ${dir}`);
  }

  // 1. Manifest-driven pairing
  const manifestPath = path.join(dir, 'pairs.json');
  if (fs.existsSync(manifestPath)) {
    const entries = JSON.parse(fs.readFileSync(manifestPath, 'utf8')) as ManifestEntry[];
    return entries.map(e => ({
      name:  e.name,
      front: path.join(dir, e.front),
      back:  path.join(dir, e.back),
    }));
  }

  // 2. Auto-discovery by filename prefix
  const files  = fs.readdirSync(dir).filter(f => IMAGE_EXTS.test(f));
  const fronts = new Map<string, string>();
  const backs  = new Map<string, string>();

  for (const file of files) {
    const parsed = stripViewSuffix(file);
    if (!parsed) continue;
    const full = path.join(dir, file);
    if (parsed.isFront) fronts.set(parsed.key, full);
    else                backs.set(parsed.key, full);
  }

  const pairs: ImagePair[] = [];
  for (const [key, frontPath] of fronts) {
    const backPath = backs.get(key);
    if (backPath) {
      pairs.push({ name: key, front: frontPath, back: backPath });
    } else {
      console.warn(`[image-pairs] No back/left image for "${key}" — skipping. Add a pairs.json to pair it explicitly.`);
    }
  }
  return pairs;
}
