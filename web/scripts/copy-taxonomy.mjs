import { copyFileSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = resolve(__dirname, "../../shared/taxonomy.json");
const dest = resolve(__dirname, "../lib/_generated/taxonomy.json");

mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log("taxonomy synced: shared/taxonomy.json → web/lib/_generated/taxonomy.json");
