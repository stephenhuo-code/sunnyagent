import type { Reporter, FullResult } from '@playwright/test/reporter';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

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

class CustomReporter implements Reporter {
  private configFile: string;
  private testsDir: string;

  constructor() {
    this.testsDir = path.resolve(__dirname, '../../../tests');
    this.configFile = path.join(this.testsDir, '.current-test-config.json');
  }

  async onEnd(result: FullResult) {
    // 等待一小段时间确保其他 reporter 完成写入
    await new Promise(resolve => setTimeout(resolve, 1000));

    // 读取配置文件
    if (!fs.existsSync(this.configFile)) {
      console.log('⚠️ No config file found');
      return;
    }

    const config = JSON.parse(fs.readFileSync(this.configFile, 'utf-8'));
    const { timestamp, reportsDir, screenshotsDir } = config;

    // 生成完成时间戳
    const endTimestamp = getLocalTimestamp();
    const newDirName = `${timestamp}_done_${endTimestamp}`;

    // 重命名 reports 目录
    if (fs.existsSync(reportsDir)) {
      const newReportDir = path.join(path.dirname(reportsDir), newDirName);
      try {
        fs.renameSync(reportsDir, newReportDir);
        console.log(`📊 Report renamed: ${newDirName}`);

        // 更新 latest 软链接
        const latestLink = path.join(path.dirname(reportsDir), 'latest');
        try { fs.unlinkSync(latestLink); } catch (e) { /* ignore */ }
        try { fs.symlinkSync(newDirName, latestLink); } catch (e) { /* ignore */ }
        console.log(`🔗 Latest report link updated`);
      } catch (e) {
        console.log(`⚠️ Failed to rename reports: ${e}`);
      }
    }

    // 重命名 screenshots 目录
    const screenshotsParentDir = path.dirname(screenshotsDir);
    const newScreenshotDir = path.join(screenshotsParentDir, newDirName);

    if (fs.existsSync(screenshotsDir)) {
      try {
        fs.renameSync(screenshotsDir, newScreenshotDir);
        console.log(`📸 Screenshots renamed: ${newDirName}`);

        // 更新 latest 软链接
        const latestLink = path.join(screenshotsParentDir, 'latest');
        try { fs.unlinkSync(latestLink); } catch (e) { /* ignore */ }
        try { fs.symlinkSync(newDirName, latestLink); } catch (e) { /* ignore */ }
        console.log(`🔗 Latest screenshots link updated`);
      } catch (e) {
        console.log(`⚠️ Failed to rename screenshots: ${e}`);
      }
    }

    // 删除配置文件
    try { fs.unlinkSync(this.configFile); } catch (e) { /* ignore */ }
  }
}

export default CustomReporter;
