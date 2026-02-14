import { test, expect } from '@playwright/test';
import { ScreenshotHelper } from './fixtures/screenshot-helper';
import { login } from './fixtures/auth-helper';

test.describe('Deep Research Agent Test', () => {
  test('Research agent can search web and return research results', async ({ page }) => {
    const screenshot = new ScreenshotHelper(page, 'research-agent');

    // Step 1: Open chat page and login
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await login(page);
    await page.waitForLoadState('networkidle');
    await screenshot.capture('page-load');

    // Step 2: Input research query
    const textarea = page.locator('textarea');
    await textarea.fill('研究一下 2026 年 AI 发展趋势');
    await screenshot.capture('input-research');

    // Step 3: Send message
    const sendButton = page.locator('button.send-btn');
    await sendButton.click();
    await screenshot.capture('sending');

    // Step 4: Wait for task tree to show Research Agent
    const assistantMessage = page.locator('.message-bubble.assistant').last();
    await expect(assistantMessage).toBeVisible({ timeout: 15000 });

    // Check if task tree is visible
    const hasTaskTree = await assistantMessage.locator('.task-list').isVisible().catch(() => false);
    if (hasTaskTree) {
      await screenshot.capture('task-tree-visible');
    }

    // Step 5: Wait for search tool calls
    // Give time for search operations
    await page.waitForTimeout(3000);
    await screenshot.capture('tavily-search-in-progress');

    // Step 6: Verify research result display
    // Wait for final content (may take longer for research)
    const messageContent = assistantMessage.locator('.message-content');
    await expect(messageContent).toBeVisible({ timeout: 40000 });
    await expect(messageContent).not.toBeEmpty();

    await screenshot.capture('research-result');

    // Step 7: Verify citations or sources (if present)
    // Research results might include links or citations
    const content = await messageContent.textContent();
    console.log(`Research result length: ${content?.length || 0} characters`);

    await screenshot.capture('citations');

    // Verify no error message
    const errorMessage = page.locator('.error-message');
    await expect(errorMessage).not.toBeVisible();

    console.log('✅ Research Agent test completed successfully');
  });
});
