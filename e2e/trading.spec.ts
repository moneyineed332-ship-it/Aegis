import { test, expect } from "@playwright/test";

test.describe("Paper Trading Flow via API", () => {
  test("can create a paper order via API", async ({ request }) => {
    const response = await request.post("http://localhost:8000/api/v1/paper-orders", {
      headers: { "X-AEGIS-Admin-Token": "e2e-test-token" },
      data: {
        symbol: "BTC/USDT",
        side: "buy",
        quantity: 0.001,
        reference_price: 50000,
      },
    });
    expect(response.ok()).toBeTruthy();
    const order = await response.json();
    expect(order).toHaveProperty("id");
  });

  test("can get positions monitor via API", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/positions/monitor");
    expect(response.ok()).toBeTruthy();
  });

  test("can get journal analysis via API", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/journal/analysis");
    expect(response.ok()).toBeTruthy();
  });

  test("can get alerts history via API", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/alerts/history");
    expect(response.ok()).toBeTruthy();
  });

  test("health/detailed returns system info", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/health/detailed");
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("status");
  });
});

test.describe("Engine Controls via UI", () => {
  test("engine section loads in dashboard", async ({ page }) => {
    await page.goto("/dashboard/engine");
    await expect(page.getByText("Chargement du moteur...")).toBeVisible();
  });

  test("learning section loads in dashboard", async ({ page }) => {
    await page.goto("/dashboard/learning");
    await expect(page.getByRole("button", { name: "Apprentissage" })).toBeVisible();
  });

  test("security section loads in dashboard", async ({ page }) => {
    await page.goto("/dashboard/security");
    await expect(page.getByRole("button", { name: "Securite" })).toBeVisible();
  });

  test("positions section loads in dashboard", async ({ page }) => {
    await page.goto("/dashboard/positions");
    await expect(page.getByText("Chargement...")).toBeVisible();
  });

  test("alerts section loads in dashboard", async ({ page }) => {
    await page.goto("/dashboard/alerts");
    await expect(page.getByText("Monitoring")).toBeVisible();
  });

  test("backtest section loads in dashboard", async ({ page }) => {
    await page.goto("/dashboard/backtest");
    await expect(page.getByRole("button", { name: "Backtests" })).toBeVisible();
  });

  test("journal section loads in dashboard", async ({ page }) => {
    await page.goto("/dashboard/journal");
    await expect(page.getByRole("button", { name: "Journal" })).toBeVisible();
  });
});
