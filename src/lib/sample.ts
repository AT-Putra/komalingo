import { appLocalDataDir, join, resolveResource } from "@tauri-apps/api/path";

/**
 * Where the sample run reads from and writes to. Both ABSOLUTE.
 *
 * The sidecar resolves a relative path against its own working directory,
 * which under Tauri is wherever the app was launched from -- not the repo, and
 * not anywhere the user can see. The first version sent "fixtures/sample.png"
 * and "out/test", and the sidecar answered with a FileNotFoundError inside the
 * 500 envelope. The page is bundled as a resource (tauri.conf.json
 * bundle.resources) so it exists in a built app as well as under `tauri dev`;
 * the output goes under the app's own data folder, where a test run cannot
 * land in a directory the user did not choose.
 */
export async function samplePaths(): Promise<{ src: string; dest: string }> {
  const [src, data] = await Promise.all([resolveResource("sample.png"), appLocalDataDir()]);
  return { src, dest: await join(data, "test") };
}
