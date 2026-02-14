import { defineConfig, devices } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

// ES module 中获取 __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 生成本地时间戳 (格式: YYYY-MM-DDTHH-mm-ss)
function getLocalTimestamp(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}-${minutes}-${seconds}`;
}

// 项目根目录下的 tests 文件夹
const testsDir = path.resolve(__dirname, '../tests');
const configFile = path.join(testsDir, '.current-test-config.json');

// 确保 tests 目录存在
fs.mkdirSync(path.join(testsDir, 'reports'), { recursive: true });
fs.mkdirSync(path.join(testsDir, 'screenshots'), { recursive: true });

// 从 config 文件读取时间戳，如果不存在则创建
let timestamp: string;
let reportsDir: string;
let screenshotsDir: string;

if (fs.existsSync(configFile)) {
  // config 文件存在，使用其中的时间戳
  const config = JSON.parse(fs.readFileSync(configFile, 'utf-8'));
  timestamp = config.timestamp;
  reportsDir = config.reportsDir;
  screenshotsDir = config.screenshotsDir;
} else {
  // config 文件不存在，创建新的
  timestamp = getLocalTimestamp();
  reportsDir = path.join(testsDir, 'reports', timestamp);
  screenshotsDir = path.join(testsDir, 'screenshots', timestamp);

  // 写入 config 文件
  const testConfig = { timestamp, reportsDir, screenshotsDir };
  fs.writeFileSync(configFile, JSON.stringify(testConfig, null, 2));
}

// Set timestamp as environment variable for screenshot helper
process.env.TEST_TIMESTAMP = timestamp;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,  // Run serially for easier debugging
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,

  // Reporter configuration - 自定义 reporter 放在最后，等待其他 reporter 完成后重命名目录
  reporter: [
    ['html', {
      outputFolder: reportsDir,
      open: 'never'
    }],
    ['json', {
      outputFile: path.join(reportsDir, 'summary.json')
    }],
    ['list'],
    ['./tests/e2e/custom-reporter.ts']
  ],

  use: {
    baseURL: 'http://localhost:3008',

    // Screenshot configuration
    screenshot: 'on',  // Screenshot every test step

    // Video configuration - retain on failure
    video: 'retain-on-failure',

    // Trace configuration - retain on failure
    trace: 'retain-on-failure',

    // Timeout configuration
    actionTimeout: 10000,
    navigationTimeout: 30000,
  },

  // Output directory - 使用单独的目录，避免和 screenshot-helper 冲突
  // Playwright 会在这里存储 test artifacts (traces, videos, etc.)
  outputDir: path.join(testsDir, 'artifacts', timestamp),

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
