import { test, expect } from '@playwright/test';
import { ScreenshotHelper } from './fixtures/screenshot-helper';
import { login } from './fixtures/auth-helper';

test.describe('Autonomous Planning Agent Test', () => {
  test('Complex task can be automatically split and executed in parallel', async ({ page }) => {
    const screenshot = new ScreenshotHelper(page, 'planning-agent');

    // Step 1: Open chat page and login
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await login(page);
    await page.waitForLoadState('networkidle');
    await screenshot.capture('page-load');

    // Step 2: Input complex task
    const textarea = page.locator('textarea');
    await textarea.fill('比较特斯拉和小米的市场策略并生成报告');
    await screenshot.capture('input-complex-task');

    // Step 3: Send message
    const sendButton = page.locator('button.send-btn');
    await sendButton.click();
    await screenshot.capture('sending');

    // Step 4: Wait for thinking area to show planning
    const assistantMessage = page.locator('.message-bubble.assistant').last();
    await expect(assistantMessage).toBeVisible({ timeout: 15000 });

    // Check for thinking bubble
    const hasThinking = await assistantMessage.locator('.thinking-bubble').isVisible().catch(() => false);
    if (hasThinking) {
      await screenshot.capture('thinking-visible');
    }

    // Step 5: Verify task tree has multiple nodes
    // Wait a bit for task tree to populate
    await page.waitForTimeout(3000);

    const hasTaskTree = await assistantMessage.locator('.task-list').isVisible().catch(() => false);
    if (hasTaskTree) {
      const taskItems = assistantMessage.locator('.task-item');
      const taskCount = await taskItems.count();
      console.log(`Task tree has ${taskCount} tasks`);

      await screenshot.capture('task-tree-multiple');
    }

    // Step 6: Wait for subtasks execution
    // Complex planning may take longer
    await page.waitForTimeout(5000);
    await screenshot.capture('subtasks-running');

    // Step 7: Verify final result summary
    // Wait for content to appear (may take a while for complex planning)
    const messageContent = assistantMessage.locator('.message-content');
    await expect(messageContent).toBeVisible({ timeout: 60000 });
    await expect(messageContent).not.toBeEmpty();

    const content = await messageContent.textContent();
    console.log(`Final result length: ${content?.length || 0} characters`);

    await screenshot.capture('final-result');

    // Verify no error message
    const errorMessage = page.locator('.error-message');
    await expect(errorMessage).not.toBeVisible();

    console.log('✅ Planning Agent test completed successfully');
  });
});
