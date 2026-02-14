import { Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export class ScreenshotHelper {
  private page: Page;
  private scenarioName: string;
  private stepCounter: number = 0;
  private baseDir: string;

  constructor(page: Page, scenarioName: string) {
    this.page = page;
    this.scenarioName = scenarioName;

    // 从配置文件读取截图目录
    const testsDir = path.join(__dirname, '../../../../tests');
    const configFile = path.join(testsDir, '.current-test-config.json');
    let screenshotsDir: string;

    if (fs.existsSync(configFile)) {
      const config = JSON.parse(fs.readFileSync(configFile, 'utf-8'));
      screenshotsDir = config.screenshotsDir;
    } else {
      const timestamp = process.env.TEST_TIMESTAMP ||
        new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      screenshotsDir = path.join(testsDir, 'screenshots', timestamp);
    }

    this.baseDir = path.join(screenshotsDir, scenarioName);

    // Ensure directory exists
    fs.mkdirSync(this.baseDir, { recursive: true });
  }

  async capture(stepName: string, options?: { fullPage?: boolean }) {
    this.stepCounter++;
    const filename = `${String(this.stepCounter).padStart(2, '0')}-${stepName}.png`;
    const filepath = path.join(this.baseDir, filename);

    await this.page.screenshot({
      path: filepath,
      fullPage: options?.fullPage ?? true
    });

    console.log(`📸 Screenshot saved: ${filepath}`);
    return filepath;
  }

  // Capture specific element
  async captureElement(selector: string, stepName: string) {
    this.stepCounter++;
    const filename = `${String(this.stepCounter).padStart(2, '0')}-${stepName}.png`;
    const filepath = path.join(this.baseDir, filename);

    const element = this.page.locator(selector);
    await element.screenshot({ path: filepath });

    console.log(`📸 Element screenshot saved: ${filepath}`);
    return filepath;
  }
}
