import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test("navigates from landing to dashboard overview", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "ACCÈS SYSTÈME" }).click();
    await expect(page).toHaveURL(/\/dashboard\/overview/);
  });

  test("dashboard redirects /dashboard to /dashboard/overview", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard\/overview/);
  });

  test("sidebar renders navigation items", async ({ page }) => {
    await page.goto("/dashboard/overview");
    await expect(page.getByRole("button", { name: "Vue d'ensemble" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Portefeuille", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Moteur" }).first()).toBeVisible();
  });

  test("navigates to engine section via sidebar", async ({ page }) => {
    await page.goto("/dashboard/overview");
    await page.getByRole("button", { name: "Moteur" }).first().click();
    await expect(page).toHaveURL(/\/dashboard\/engine/);
  });

  test("navigates to portfolio section via URL", async ({ page }) => {
    await page.goto("/dashboard/portfolio");
    await expect(page).toHaveURL(/\/dashboard\/portfolio/);
  });

  test("navigates to risk section via URL", async ({ page }) => {
    await page.goto("/dashboard/risk");
    await expect(page).toHaveURL(/\/dashboard\/risk/);
  });

  test("404 route redirects to landing", async ({ page }) => {
    await page.goto("/does-not-exist");
    await expect(page).toHaveURL("/");
  });
});

test.describe("Dashboard API Integration", () => {
  test("API health endpoint returns 200", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/health");
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("status");
  });

  test("dashboard endpoint returns data with positions", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/dashboard");
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("positions");
    expect(body).toHaveProperty("risk");
  });

  test("engine status endpoint returns data", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/engine/status");
    expect(response.ok()).toBeTruthy();
  });

  test("oms orders endpoint returns data", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/oms/orders");
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(Array.isArray(body)).toBeTruthy();
  });

  test("strategies endpoint returns data", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/strategies");
    expect(response.ok()).toBeTruthy();
  });

  test("metrics endpoint returns prometheus text", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/metrics");
    expect(response.ok()).toBeTruthy();
    const text = await response.text();
    expect(text).toContain("aegis_");
  });

  test("health/detailed returns system info", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/health/detailed");
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("status");
  });

  test("positions monitor endpoint returns data", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/positions/monitor");
    expect(response.ok()).toBeTruthy();
  });

  test("alerts history endpoint returns data", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/alerts/history");
    expect(response.ok()).toBeTruthy();
  });

  test("journal analysis endpoint returns data", async ({ request }) => {
    const response = await request.get("http://localhost:8000/api/v1/journal/analysis");
    expect(response.ok()).toBeTruthy();
  });
});
