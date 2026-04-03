import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { writeFileSync, unlinkSync } from 'fs';
import { resolve, join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const API_BASE = 'http://localhost:18041';
const TEST_PROFILE = '_pw_x12_test';
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..');

function cleanupProfile(profileName: string): void {
  const scriptPath = join(PROJECT_ROOT, '_pw_cleanup.py');
  const script = [
    'import yaml',
    'from pathlib import Path',
    `cfg = Path(r"${join(PROJECT_ROOT, 'config', 'config.yaml')}")`,
    'data = yaml.safe_load(cfg.read_text())',
    `data.get("compare",{}).get("profiles",{}).pop("${profileName}", None)`,
    `data.get("csv_schema_registry",{}).pop("${profileName}", None)`,
    'cfg.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))',
    `Path(r"${join(PROJECT_ROOT, 'config', 'compare_rules', profileName + '.yaml')}").unlink(missing_ok=True)`,
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

  test('Onboard page shows X12 EDI and Flat-File format options', async ({ page }) => {
    await page.goto('/#onboard');
    await page.waitForTimeout(2000);

    const x12Btn = page.getByText('X12 EDI');
    const flatBtn = page.getByText('Flat-File / XML');

    await expect(x12Btn).toBeVisible();
    await expect(flatBtn).toBeVisible();

    // Both should be clickable buttons
    const x12El = page.locator('button', { hasText: 'X12 EDI' });
    const flatEl = page.locator('button', { hasText: 'Flat-File / XML' });
    await expect(x12El).toBeEnabled();
    await expect(flatEl).toBeEnabled();
  });
});
