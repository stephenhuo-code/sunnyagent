import { Page } from '@playwright/test';

export async function login(page: Page, username: string = 'admin', password: string = 'admin123') {
  // Check if login form exists
  const usernameInput = page.locator('input#username');
  const isLoginPage = await usernameInput.count() > 0;

  if (isLoginPage) {
    // Fill in login form using ID selectors
    await page.locator('input#username').fill(username);
    await page.locator('input#password').fill(password);

    // Click login button
    await page.locator('button[type="submit"]').click();

    // Wait for navigation to chat page (wait for textarea to appear)
    await page.waitForSelector('textarea', { timeout: 10000 });
  }
}
