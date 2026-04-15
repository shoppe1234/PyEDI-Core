import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { writeFileSync, unlinkSync, readFileSync } from 'fs';
import { resolve, join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const TEST_PROFILE = '_pw_x12_855_test';
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..');

function cleanupProfile(profileName: string): void {
  const scriptPath = join(PROJECT_ROOT, '_pw_cleanup_855.py');
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
    // best-effort
  } finally {
    try { unlinkSync(scriptPath); } catch { /* ignore */ }
  }
}

async function navigateTo855Schema(page: any) {
  await page.goto('/#onboard');
  await page.waitForTimeout(2000);
  await page.locator('button', { hasText: 'X12 EDI' }).click();
  await page.waitForTimeout(2000);

  // Select 4010 in version dropdown
  const versionSelect = page.locator('select');
  await versionSelect.selectOption('4010');
  await page.waitForTimeout(2000);

  const searchInput = page.locator('input[placeholder="Search transaction types..."]');
  await searchInput.fill('855');
  await page.waitForTimeout(500);
  await page.locator('button', { hasText: /^855/ }).first().click();
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'Review Schema' }).click();
  await page.waitForTimeout(2500);
}

test.describe('X12 855 Required Segments + Severity', () => {
  test.afterEach(() => cleanupProfile(TEST_PROFILE));

  test('Required Segments dd shows only mandatory segments (ST, BAK, SE)', async ({ page }) => {
    await navigateTo855Schema(page);

    const requiredDd = page.locator('dt', { hasText: 'Required Segments' }).locator('xpath=following-sibling::dd[1]');
    await expect(requiredDd).toBeVisible();
    const text = (await requiredDd.textContent()) || '';

    // Mandatory at root in stock 004010/855 schema
    expect(text).toContain('ST');
    expect(text).toContain('BAK');
    expect(text).toContain('SE');

    // Optional segments must NOT appear
    const optional = ['CUR', 'REF', 'PER', 'TAX', 'FOB', 'CTP', 'PAM', 'CSH', 'SAC', 'ITD', 'DIS', 'INC', 'DTM',
      'LDT', 'SI', 'PID', 'MEA', 'PWK', 'PKG', 'TD1', 'TD5', 'TD3', 'TD4', 'MAN', 'TXI', 'CTB', 'N9', 'MSG',
      'N1', 'N2', 'N3', 'N4', 'NX2', 'ADV', 'MTX', 'PO3', 'PO4', 'IT8', 'SDQ', 'AMT'];
    const tokens = new Set(text.split(',').map(s => s.trim()));
    for (const seg of optional) {
      expect(tokens.has(seg), `optional ${seg} should not be in Required Segments`).toBeFalsy();
    }
  });

  test('Rules step seeds severity from min_occurs (BAK01 hard, CUR01 soft)', async ({ page }) => {
    await navigateTo855Schema(page);

    await page.getByRole('button', { name: 'Next: Register Partner' }).click();
    await page.waitForTimeout(2000);

    await page.locator('input[placeholder="bevager_810"]').fill(TEST_PROFILE);
    await page.locator('input[placeholder="Bevager"]').fill('PW 855 Test');
    await page.getByRole('button', { name: 'Register' }).click();
    await page.waitForTimeout(3000);

    await page.getByRole('button', { name: 'Next: Configure Rules' }).click();
    await page.waitForTimeout(2500);

    // BAK01 row — mandatory segment + mandatory element → hard
    const bakRow = page.locator('tr', { hasText: 'BAK01' }).first();
    await expect(bakRow).toBeVisible();
    const bakSeverity = bakRow.locator('select').first();
    await expect(bakSeverity).toHaveValue('hard');

    // CUR01 row — optional segment → soft
    const curRow = page.locator('tr', { hasText: 'CUR01' }).first();
    await expect(curRow).toBeVisible();
    const curSeverity = curRow.locator('select').first();
    await expect(curSeverity).toHaveValue('soft');

    // PER02 — optional segment → soft
    const perRow = page.locator('tr', { hasText: 'PER02' }).first();
    await expect(perRow).toBeVisible();
    await expect(perRow.locator('select').first()).toHaveValue('soft');
  });

  test('Tier rules (BAK01) appear as inherited badge in StepRules', async ({ page }) => {
    await navigateTo855Schema(page);

    await page.getByRole('button', { name: 'Next: Register Partner' }).click();
    await page.waitForTimeout(2000);

    await page.locator('input[placeholder="bevager_810"]').fill(TEST_PROFILE);
    await page.locator('input[placeholder="Bevager"]').fill('PW 855 Test');
    await page.getByRole('button', { name: 'Register' }).click();
    await page.waitForTimeout(3000);

    await page.getByRole('button', { name: 'Next: Configure Rules' }).click();
    await page.waitForTimeout(2500);

    const bakRow = page.locator('tr', { hasText: 'BAK01' }).first();
    await expect(bakRow).toBeVisible();
    await expect(bakRow.getByText(/inherited from _global_855\.yaml/)).toBeVisible();
    await expect(bakRow.getByRole('button', { name: 'Override' })).toBeVisible();
  });

  test('Saved partner YAML omits inherited classification rows', async ({ page }) => {
    await navigateTo855Schema(page);

    await page.getByRole('button', { name: 'Next: Register Partner' }).click();
    await page.waitForTimeout(2000);

    await page.locator('input[placeholder="bevager_810"]').fill(TEST_PROFILE);
    await page.locator('input[placeholder="Bevager"]').fill('PW 855 Test');
    await page.getByRole('button', { name: 'Register' }).click();
    await page.waitForTimeout(3000);

    await page.getByRole('button', { name: 'Next: Configure Rules' }).click();
    await page.waitForTimeout(2500);

    await page.getByRole('button', { name: 'Save Rules' }).click();
    await page.waitForTimeout(3000);
    await expect(page.getByText('Trading Partner Onboarded')).toBeVisible();

    const path = join(PROJECT_ROOT, 'config', 'compare_rules', `${TEST_PROFILE}.yaml`);
    const body = readFileSync(path, 'utf8');

    expect(body).not.toMatch(/field:\s*BAK01/);
    expect(body).not.toMatch(/field:\s*PO102/);
    expect(body).not.toMatch(/field:\s*CTT01/);

    expect(body).toMatch(/segment:\s*['"]?\*/);
  });
});
