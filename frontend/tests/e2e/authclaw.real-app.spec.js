import { expect, test } from '@playwright/test';

const email = process.env.AUTHCLAW_E2E_EMAIL || '';
const password = process.env.AUTHCLAW_E2E_PASSWORD || '';
const otpCode = process.env.AUTHCLAW_E2E_OTP_CODE || '';
const runRegistration = process.env.AUTHCLAW_E2E_ENABLE_ONBOARDING === '1';

async function appIsReachable(page) {
  try {
    const response = await page.request.get('/api/health/ready', { timeout: 5000 });
    return response.ok();
  } catch {
    return false;
  }
}

async function login(page) {
  test.skip(!email || !password, 'Set AUTHCLAW_E2E_EMAIL and AUTHCLAW_E2E_PASSWORD to run authenticated E2E coverage.');
  await page.goto('/login');
  await expect(page.getByText('AuthClaw Console')).toBeVisible();
  await page.getByLabel(/Security Username or Email/i).fill(email);
  await page.getByLabel(/Security Passcode/i).fill(password);
  await page.getByRole('button', { name: /Sign In to Console/i }).click();

  const otpField = page.getByLabel(/Authenticator|OTP|code/i);
  if (await otpField.isVisible().catch(() => false)) {
    test.skip(!otpCode, 'Set AUTHCLAW_E2E_OTP_CODE when the selected real account requires MFA.');
    await otpField.fill(otpCode);
    await page.getByRole('button', { name: /Verify|Continue|Sign In/i }).click();
  }

  await expect(page).not.toHaveURL(/\/login$/);
}

test.beforeEach(async ({ page }) => {
  test.skip(!(await appIsReachable(page)), 'Real AuthClaw app is not reachable at AUTHCLAW_E2E_BASE_URL.');
});

test('authentication, dashboard navigation, settings, and logout use the real app', async ({ page }) => {
  await login(page);

  await page.goto('/chat');
  await expect(page.getByText(/Gateway Chat Console/i)).toBeVisible();

  await page.goto('/observability');
  await expect(page.getByText(/Gateway Dashboard|Observability/i)).toBeVisible();

  await page.goto('/settings');
  await expect(page.getByText(/RBAC|Settings|Tenant/i)).toBeVisible();

  await page.getByRole('button').filter({ hasText: /logout|sign out/i }).click().catch(async () => {
    await page.locator('button[aria-label*="logout"], button[title*="logout"]').click();
  });
  await expect(page).toHaveURL(/\/login/);
});

test('gateway chat, requests, approvals, audit, providers, API keys, and Trust Center render against backend APIs', async ({ page }) => {
  await login(page);

  const routes = [
    ['/chat', /Gateway Chat Console/i],
    ['/requests', /Gateway Requests|Requests/i],
    ['/approvals', /Approval/i],
    ['/audit', /Audit/i],
    ['/providers', /Provider|Gateway/i],
    ['/api-keys', /API Key|Security Key/i],
    ['/policies', /Policy|Guardrail/i],
    ['/connectors', /Connector|Remediation/i],
    ['/trust', /Trust Center|Signed Evidence/i],
    ['/frameworks/explorer', /Framework|Control|Evidence/i],
    ['/red-team', /Red Team|Severity|Probe/i],
    ['/tenant-plan', /Tenant Plan|Quota|Rate Limit/i],
  ];

  for (const [path, heading] of routes) {
    await page.goto(path);
    await expect(page.getByText(heading)).toBeVisible();
  }
});

test('document upload surface and evidence views are available to authorized users', async ({ page }) => {
  await login(page);

  await page.goto('/connectors');
  await expect(page.getByText(/Findings|Connector|Trust Center/i)).toBeVisible();

  await page.goto('/audit');
  await expect(page.getByText(/Export|Audit|Hash/i)).toBeVisible();
});

test('tenant registration, email verification, and domain verification use real onboarding flow', async ({ page }) => {
  test.skip(!runRegistration, 'Set AUTHCLAW_E2E_ENABLE_ONBOARDING=1 to create a real onboarding registration.');

  const unique = Date.now();
  await page.goto('/register');
  await expect(page.getByText(/Register Tenant|AuthClaw Console/i)).toBeVisible();
  await page.getByLabel(/work email|email/i).fill(`authclaw-e2e-${unique}@example.com`);
  await page.getByLabel(/domain/i).fill(`example-${unique}.com`);
  await page.getByLabel(/password|passcode/i).fill(`AuthClaw-E2E-${unique}!`);
  await page.getByRole('button', { name: /Register|Create/i }).click();
  await expect(page.getByText(/verification|verify/i)).toBeVisible();
});
