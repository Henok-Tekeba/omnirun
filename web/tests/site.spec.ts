import { expect, test } from "@playwright/test";

test("cookie notice, mobile menu, and legal pages", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.viewport);

  const banner = page.locator(".cookie-consent");
  await expect(banner).toBeVisible();
  await page.getByRole("button", { name: "Accept" }).click();
  await expect(banner).toBeHidden();

  await page.reload();
  await expect(banner).toBeHidden();

  await page.getByRole("button", { name: "Open menu" }).click();
  await expect(page.locator("#marketing-mobile-menu")).toBeVisible();
  await page
    .locator("#marketing-mobile-menu")
    .getByRole("link", { name: "Privacy" })
    .click();
  await expect(page.getByRole("heading", { name: "Privacy policy" })).toBeVisible();

  const legalBodySize = await page
    .locator(".legal-article p")
    .first()
    .evaluate((element) => parseFloat(getComputedStyle(element).fontSize));
  expect(legalBodySize).toBeGreaterThanOrEqual(16);

  await page.locator(".legal-nav").getByRole("link", { name: "Terms" }).click();
  await expect(page.getByRole("heading", { name: "Terms & conditions" })).toBeVisible();

  await page.locator(".site-footer").getByRole("button", { name: "Cookie settings" }).click();
  await expect(banner).toBeVisible();
});
