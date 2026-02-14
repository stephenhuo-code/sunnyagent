import { test, expect } from '@playwright/test';
import { ScreenshotHelper } from './fixtures/screenshot-helper';
import { login } from './fixtures/auth-helper';

test.describe('Simple Chat Return', () => {
  test('User sends simple question, system directly returns answer', async ({ page }) => {
    const screenshot = new ScreenshotHelper(page, 'simple-chat');

    // Step 1: Open chat page and login
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await login(page);
    await page.waitForLoadState('networkidle');
    await screenshot.capture('page-load');

    // Step 2: Input message
    const textarea = page.locator('textarea');
    await textarea.fill('你是谁');
    await screenshot.capture('input-message');

    // Step 3: Click send button
    const sendButton = page.locator('button.send-btn');
    await sendButton.click();
    await screenshot.capture('sending');

    // Step 4: Wait for response
    // Wait for assistant message to appear
    const assistantMessage = page.locator('.message-bubble.assistant').last();
    await expect(assistantMessage).toBeVisible({ timeout: 10000 });

    // Wait for content to appear
    const messageContent = assistantMessage.locator('.message-content');
    await expect(messageContent).toBeVisible({ timeout: 10000 });
    await expect(messageContent).not.toBeEmpty();

    await screenshot.capture('response-received');

    // Step 5: Verify final interface state
    // Verify no task tree is displayed (simple chat scenario)
    const taskTree = page.locator('.task-list');
    await expect(taskTree).not.toBeVisible();

    // Verify no error message
    const errorMessage = page.locator('.error-message');
    await expect(errorMessage).not.toBeVisible();

    await screenshot.capture('final-state');

    console.log('✅ Simple chat test completed successfully');
  });
});
