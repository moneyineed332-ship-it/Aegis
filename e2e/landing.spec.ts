import { test, expect } from "@playwright/test";

test.describe("Landing Page", () => {
  test("renders the landing page with AEGIS branding", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("banner").getByText("AEGIS AI QUANT")).toBeVisible();
  });

  test("displays hero title and subtitle", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Trading Crypto")).toBeVisible();
    await expect(page.getByText("Piloté par l'IA")).toBeVisible();
  });

  test("displays feature benefits section", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Arrêt d'urgence")).toBeVisible();
    await expect(page.getByText("Traçabilité totale")).toBeVisible();
  });

  test("displays workflow steps", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Collecte & Analyse")).toBeVisible();
    await expect(page.getByText("Décision IA")).toBeVisible();
    await expect(page.getByText("Exécution & Apprentissage")).toBeVisible();
  });

  test("ACCÈS SYSTÈME button navigates to dashboard", async ({ page }) => {
    await page.goto("/");
    const btn = page.getByRole("button", { name: "ACCÈS SYSTÈME" });
    await expect(btn).toBeVisible();
    await btn.click();
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("displays LANCER LE DASHBOARD button", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("LANCER LE DASHBOARD")).toBeVisible();
  });
});
