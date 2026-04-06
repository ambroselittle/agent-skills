import { expect, type Page } from "@playwright/test"

export abstract class BasePage {
  protected readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  abstract get path(): string

  async navigate(): Promise<void> {
    await this.page.goto(this.path)
  }

  async waitForReady(): Promise<void> {
    await expect(this.page.locator("body")).toBeVisible()
  }
}
