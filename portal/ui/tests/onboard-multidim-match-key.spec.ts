import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { writeFileSync, unlinkSync, readFileSync } from 'fs';
import { resolve, join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const TEST_PROFILE = '_pw_multidim_test';
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..');

function cleanupProfile(profileName: string): void {
  const scriptPath = join(PROJECT_ROOT, '_pw_cleanup_multidim.py');
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
  } catch { /* best-effort */ }
  finally { try { unlinkSync(scriptPath); } catch { /* ignore */ } }
}

async function gotoRegister855(page: any) {
  await page.goto('/#onboard');
  await page.waitForTimeout(2000);
  await page.locator('button', { hasText: 'X12 EDI' }).click();
  await page.waitForTimeout(2000);
  await page.locator('select').selectOption('4010');
  await page.waitForTimeout(2000);
  await page.locator('input[placeholder="Search transaction types..."]').fill('855');
  await page.waitForTimeout(500);
  await page.locator('button', { hasText: /^855/ }).first().click();
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'Review Schema' }).click();
  await page.waitForTimeout(2500);
  await page.getByRole('button', { name: 'Next: Register Partner' }).click();
  await page.waitForTimeout(2000);
}

test.describe('Onboard Multi-Dimensional Match Key', () => {
  test.afterEach(() => cleanupProfile(TEST_PROFILE));

  test('Register 855 with 2 X12 match keys persists list in config.yaml', async ({ page }) => {
    await gotoRegister855(page);

    await page.locator('input[placeholder="bevager_810"]').fill(TEST_PROFILE);
    await page.locator('input[placeholder="Bevager"]').fill('PW Multidim Test');

    const segInputs = page.locator('input[placeholder="BIG"]');
    await expect(segInputs.first()).not.toHaveValue('');

    await page.getByRole('button', { name: '+ Add key' }).click();
    await page.waitForTimeout(300);
    await segInputs.nth(1).fill('PO1');
    const fieldInputs = page.locator('input[placeholder="BIG02"]');
    await fieldInputs.nth(1).fill('PO101');

    await page.getByRole('button', { name: 'Register' }).click();
    await page.waitForTimeout(3000);
    await expect(page.getByText('Partner registered successfully')).toBeVisible();

    const cfgPath = join(PROJECT_ROOT, 'config', 'config.yaml');
    const body = readFileSync(cfgPath, 'utf8');
    expect(body).toMatch(new RegExp(`${TEST_PROFILE}:`));
    expect(body).toMatch(/match_key:\s*[\s\S]*?segment:\s*BAK[\s\S]*?segment:\s*PO1/);
  });

  test('Remove button returns to singleton dict form', async ({ page }) => {
    await gotoRegister855(page);

    await page.locator('input[placeholder="bevager_810"]').fill(TEST_PROFILE);
    await page.locator('input[placeholder="Bevager"]').fill('PW Multidim Test');

    await page.getByRole('button', { name: '+ Add key' }).click();
    await page.waitForTimeout(200);
    await page.getByRole('button', { name: 'Remove' }).last().click();
    await page.waitForTimeout(200);

    await page.getByRole('button', { name: 'Register' }).click();
    await page.waitForTimeout(3000);
    await expect(page.getByText('Partner registered successfully')).toBeVisible();

    const body = readFileSync(join(PROJECT_ROOT, 'config', 'config.yaml'), 'utf8');
    const profileBlock = body.split(`${TEST_PROFILE}:`)[1]?.split('\n\n')[0] || '';
    expect(profileBlock).toMatch(/match_key:\s*\n\s+segment:/);
    expect(profileBlock).not.toMatch(/match_key:\s*\n\s+-\s+segment:/);
  });
});
