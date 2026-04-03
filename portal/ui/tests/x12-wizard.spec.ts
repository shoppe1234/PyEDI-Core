import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { writeFileSync, unlinkSync, existsSync } from 'fs';
import * as path from 'path';

const API_BASE = 'http://localhost:18041';
const TEST_PROFILE = '_pw_x12_test';
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');

function cleanupProfile(profileName: string): void {
  const scriptPath = path.join(PROJECT_ROOT, '_pw_cleanup.py');
  const script = [
    'import yaml',
    'from pathlib import Path',
    `cfg = Path(r"${path.join(PROJECT_ROOT, 'config', 'config.yaml')}")`,
    'data = yaml.safe_load(cfg.read_text())',
    `data.get("compare",{}).get("profiles",{}).pop("${profileName}", None)`,
    `data.get("csv_schema_registry",{}).pop("${profileName}", None)`,
    'cfg.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))',
    `Path(r"${path.join(PROJECT_ROOT, 'config', 'compare_rules', profileName + '.yaml')}").unlink(missing_ok=True)`,
  ].join('\n');
  try {
    writeFileSync(scriptPath, script);
    execSync(`python "${scriptPath}"`, { cwd: PROJECT_ROOT });
  } catch {
    // best-effort cleanup
  } finally {
    try { unlinkSync(scriptPath); } catch { /* ignore */ }
  }
}

test.describe('X12 Wizard E2E', () => {
  test.afterEach(async () => {
    cleanupProfile(TEST_PROFILE);
  });
});
