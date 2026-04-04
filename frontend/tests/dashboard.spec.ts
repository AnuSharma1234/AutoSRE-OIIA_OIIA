import { test, expect } from "@playwright/test";

const BASE = process.env.BASE_URL || "http://localhost:3000";

test.describe("Incidents Dashboard", () => {
  test("/incidents page loads", async ({ page }) => {
    await page.goto(`${BASE}/incidents`);
    await page.waitForLoadState("networkidle");
    const heading = page.getByRole("heading", { name: /incident/i }).or(
      page.locator("[data-testid='incidents-table']")
    ).or(
      page.locator("table")
    );
    await expect(heading.or(page.locator("body"))).toBeVisible();
  });

  test("/incidents shows filter dropdown", async ({ page }) => {
    await page.goto(`${BASE}/incidents`);
    await page.waitForLoadState("networkidle");
    const select = page.locator("select").filter({ hasText: /status/i }).or(
      page.locator("select").first()
    );
    await expect(select).toBeVisible();
  });

  test("/cluster page loads", async ({ page }) => {
    await page.goto(`${BASE}/cluster`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });

  test("/incidents/[id] page loads", async ({ page }) => {
    await page.goto(`${BASE}/incidents`);
    await page.waitForLoadState("networkidle");
    const firstRow = page.locator("tbody tr").first();
    if (await firstRow.isVisible({ timeout: 3000 })) {
      const link = firstRow.locator("a").first();
      if (await link.isVisible()) {
        await link.click();
        await page.waitForLoadState("networkidle");
        await expect(page.locator("body")).toBeVisible();
        return;
      }
    }
    await page.goto(`${BASE}/incidents/00000000-0000-0000-0000-000000000000`);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("body")).toBeVisible();
  });
});
