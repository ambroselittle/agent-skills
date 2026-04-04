import { expect } from "@playwright/test"
import { BasePage } from "./base.page"

export class HomePage extends BasePage {
  get path(): string {
    return "/"
  }

  async getHeading() {
    return this.page.getByRole("heading", { level: 1 })
  }

  async getApiStatus() {
    return this.page.getByText("API status:", { exact: false })
  }

  async waitForApiReady(): Promise<void> {
    await expect(this.page.getByText("API status:", { exact: false })).not.toContainText("loading...", { timeout: 15_000 })
  }
}
