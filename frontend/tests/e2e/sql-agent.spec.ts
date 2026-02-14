import { test, expect } from '@playwright/test';
import { ScreenshotHelper } from './fixtures/screenshot-helper';
import { login } from './fixtures/auth-helper';

test.describe('SQL Agent Test', () => {
  test('SQL Agent can query database and return results', async ({ page }) => {
    const screenshot = new ScreenshotHelper(page, 'sql-agent');

    // Step 1: Open chat page and login
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await login(page);
    await page.waitForLoadState('networkidle');
    await screenshot.capture('page-load');

    // Step 2: Input SQL query
    const textarea = page.locator('textarea');
    await textarea.fill('/sql 销量最高的专辑是什么');
    await screenshot.capture('input-sql-query');

    // Step 3: Send message
    const sendButton = page.locator('button.send-btn');
    await sendButton.click();
    await screenshot.capture('sending');

    // Step 4: Wait for task tree to show SQL Agent
    // Wait for assistant message
    const assistantMessage = page.locator('.message-bubble.assistant').last();
    await expect(assistantMessage).toBeVisible({ timeout: 15000 });

    // Check if task tree or tool calls are visible
    const hasTaskTree = await assistantMessage.locator('.task-list').isVisible().catch(() => false);
    const hasToolCalls = await assistantMessage.locator('.tool-call-card').isVisible().catch(() => false);

    if (hasTaskTree || hasToolCalls) {
      await screenshot.capture('task-tree-or-tools-visible');
    }

    // Step 5: Wait for tool calls or result
    // Wait for content to appear (either tool calls or final result)
    await page.waitForTimeout(2000); // Give time for any tool calls to show
    await screenshot.capture('tool-calls-or-processing');

    // Step 6: Verify query result display
    // Wait for final content
    const messageContent = assistantMessage.locator('.message-content');
    await expect(messageContent).toBeVisible({ timeout: 30000 });
    await expect(messageContent).not.toBeEmpty();

    await screenshot.capture('query-result');

    // Verify no error message
    const errorMessage = page.locator('.error-message');
    await expect(errorMessage).not.toBeVisible();

    console.log('✅ SQL Agent test completed successfully');
  });
});
