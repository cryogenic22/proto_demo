import { test, expect } from "@playwright/test";

// Use the backend API directly to verify data, then test frontend rendering
const API = process.env.E2E_API_URL || "https://protoextract-production.up.railway.app";

test.describe("Protocol Library", () => {
  test("loads and displays protocol cards", async ({ page }) => {
    await page.goto("/protocols");
    // Wait for page heading to render
    await expect(page.locator("h2").filter({ hasText: "Protocol Library" })).toBeVisible();
    // Should have at least one protocol card
    const cards = page.locator("a[href^='/protocols/']");
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test("protocol cards show metadata", async ({ page }) => {
    await page.goto("/protocols");
    await page.waitForSelector("a[href^='/protocols/']", { timeout: 10_000 });
    // At least one card should show a sponsor name
    const pageText = await page.textContent("body");
    // Check for any real sponsor data
    const hasSponsor =
      pageText?.includes("Pfizer") ||
      pageText?.includes("AstraZeneca") ||
      pageText?.includes("Bristol") ||
      pageText?.includes("UCB") ||
      pageText?.includes("Sponsor");
    expect(hasSponsor).toBeTruthy();
  });
});

test.describe("Protocol Workspace", () => {
  // Use pfizer_bnt162 which has sections + tables + budget
  const protocolId = "pfizer_bnt162";

  test("loads workspace with section tree", async ({ page }) => {
    await page.goto(`/protocols/${protocolId}`);
    // Should show sections panel
    await expect(page.locator("h3").filter({ hasText: "Sections" })).toBeVisible({ timeout: 10_000 });
    // Should show at least one section in the tree
    const sectionButtons = page.locator("button").filter({ hasText: /PROTOCOL SUMMARY|INTRODUCTION|OBJECTIVES/ });
    await expect(sectionButtons.first()).toBeVisible({ timeout: 10_000 });
  });

  test("clicking section shows content", async ({ page }) => {
    await page.goto(`/protocols/${protocolId}`);
    await page.waitForSelector("h3:has-text('Sections')", { timeout: 10_000 });
    // Click on a section
    const introSection = page.locator("button").filter({ hasText: "INTRODUCTION" });
    if (await introSection.count() > 0) {
      await introSection.first().click();
      // Content area should show section heading
      await expect(page.locator(".section-content")).toBeVisible({ timeout: 5_000 });
    }
  });

  test("tables tab shows table cards", async ({ page }) => {
    await page.goto(`/protocols/${protocolId}`);
    await page.waitForSelector("h3:has-text('Sections')", { timeout: 10_000 });
    // Click Tables tab
    const tablesTab = page.locator("button").filter({ hasText: /^Tables/ });
    await tablesTab.click();
    // Should show table cards (pfizer_bnt162 has 9 tables)
    const tableCards = page.locator("button").filter({ hasText: /SOA|Table/ });
    await expect(tableCards.first()).toBeVisible({ timeout: 5_000 });
  });

  test("clicking table opens detail view with grid", async ({ page }) => {
    await page.goto(`/protocols/${protocolId}`);
    await page.waitForSelector("h3:has-text('Sections')", { timeout: 10_000 });
    // Click Tables tab
    await page.locator("button").filter({ hasText: /^Tables/ }).click();
    await page.waitForTimeout(2000);
    // Click first table card
    const tableCards = page.locator("button.w-full");
    const count = await tableCards.count();
    if (count > 0) {
      await tableCards.first().click();
      await page.waitForTimeout(1000);
      // Should show grid view or table detail
      const hasGrid = await page.locator("text=Grid View").isVisible().catch(() => false);
      const hasCells = await page.locator("td").first().isVisible().catch(() => false);
      expect(hasGrid || hasCells).toBeTruthy();
    }
  });

  test("table detail has footnotes/procedures/review tabs", async ({ page }) => {
    await page.goto(`/protocols/${protocolId}`);
    await page.waitForSelector("h3:has-text('Sections')", { timeout: 10_000 });
    await page.locator("button").filter({ hasText: /^Tables/ }).click();
    await page.waitForTimeout(2000);
    const tableCards = page.locator("button.w-full");
    const count = await tableCards.count();
    if (count > 0) {
      await tableCards.first().click();
      await page.waitForTimeout(1000);
      // Check sub-tabs exist
      const hasFn = await page.locator("button").filter({ hasText: "Footnotes" }).isVisible().catch(() => false);
      const hasProc = await page.locator("button").filter({ hasText: "Procedures" }).isVisible().catch(() => false);
      expect(hasFn || hasProc).toBeTruthy();
    }
  });

  test("close button returns to table list", async ({ page }) => {
    await page.goto(`/protocols/${protocolId}`);
    await page.waitForSelector("h3:has-text('Sections')", { timeout: 10_000 });
    await page.locator("button").filter({ hasText: /^Tables/ }).click();
    await page.waitForTimeout(1000);
    await page.locator("button").filter({ hasText: /SOA|Table/ }).first().click();
    await page.waitForTimeout(500);
    // Click close (X) button
    const closeBtn = page.locator("button svg path[d='M4 4L12 12M12 4L4 12']").locator("..");
    if (await closeBtn.count() > 0) {
      await closeBtn.click();
      // Should return to table list
      await expect(page.locator("button").filter({ hasText: /^Tables/ })).toBeVisible({ timeout: 3_000 });
    }
  });

  test("procedures tab shows procedure data", async ({ page }) => {
    await page.goto(`/protocols/${protocolId}`);
    await page.waitForSelector("h3:has-text('Sections')", { timeout: 10_000 });
    // Click Procedures tab
    await page.locator("button").filter({ hasText: /^Procedures/ }).click();
    // Should show procedure table or empty state
    const body = await page.textContent("body");
    const hasProcedures = body?.includes("Raw Name") || body?.includes("No procedures");
    expect(hasProcedures).toBeTruthy();
  });

  test("right panel shows metadata and stats", async ({ page }) => {
    await page.goto(`/protocols/${protocolId}`);
    await page.waitForSelector("h3:has-text('Sections')", { timeout: 10_000 });
    // Should show protocol details card
    await expect(page.locator("text=Protocol Details")).toBeVisible();
    // Should show quick stats
    await expect(page.locator("text=Quick Stats")).toBeVisible();
    // Should show pipeline info
    await expect(page.locator("text=Pipeline:")).toBeVisible();
  });
});

test.describe("Protocol Workspace — P-14 (large dataset)", () => {
  test("P-14 loads with 45 tables", async ({ page }) => {
    await page.goto("/protocols/p14");
    await page.waitForSelector("text=Quick Stats", { timeout: 15_000 });
    // Check stats show tables
    const body = await page.textContent("body");
    expect(body).toContain("45"); // 45 tables
  });

  test("P-14 tables tab renders without crash", async ({ page }) => {
    await page.goto("/protocols/p14");
    await page.waitForSelector("text=Quick Stats", { timeout: 15_000 });
    await page.locator("button").filter({ hasText: /^Tables/ }).click();
    // Should show table cards without crashing
    await page.waitForTimeout(2000);
    const cards = page.locator("button").filter({ hasText: /SOA|Table/ });
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe("Tools — Section Explorer", () => {
  test("loads protocol list in dropdown", async ({ page }) => {
    await page.goto("/tools/sections");
    await expect(page.getByRole("heading", { name: "Section Explorer" })).toBeVisible();
    // Select dropdown should have protocols
    const options = page.locator("select option");
    const count = await options.count();
    expect(count).toBeGreaterThan(1); // More than just "Select a protocol..."
  });

  test("selecting protocol shows section tree", async ({ page }) => {
    await page.goto("/tools/sections");
    await page.selectOption("select", "pfizer_bnt162");
    // Should show document outline
    await expect(page.locator("text=Document Outline")).toBeVisible({ timeout: 10_000 });
    // Should show section count
    await expect(page.locator("text=/\\d+ sections/")).toBeVisible();
  });
});

test.describe("Tools — Verbatim Extract", () => {
  test("loads with library mode by default", async ({ page }) => {
    await page.goto("/tools/verbatim");
    await expect(page.getByRole("heading", { name: "Verbatim Extract" })).toBeVisible();
    // Library mode button should be active
    await expect(page.locator("button").filter({ hasText: "From Protocol Library" })).toBeVisible();
  });

  test("selecting protocol shows section dropdown", async ({ page }) => {
    await page.goto("/tools/verbatim");
    // Select a protocol
    const select = page.locator("select").first();
    await select.selectOption("pfizer_bnt162");
    // Should show section dropdown
    await expect(page.locator("text=/Section.*available/")).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Navigation", () => {
  test("sidebar has all expected links", async ({ page }) => {
    await page.goto("/");
    const nav = page.locator("aside");
    await expect(nav.locator("text=Protocol Library")).toBeVisible();
    await expect(nav.locator("text=Upload New")).toBeVisible();
    await expect(nav.locator("text=Section Explorer")).toBeVisible();
    await expect(nav.locator("text=Verbatim Extract")).toBeVisible();
    await expect(nav.locator("text=Extraction Jobs")).toBeVisible();
    await expect(nav.locator("text=Quality Dashboard")).toBeVisible();
    await expect(nav.locator("text=Procedure Library")).toBeVisible();
  });

  test("golden-set link is removed", async ({ page }) => {
    await page.goto("/");
    const nav = page.locator("aside");
    await expect(nav.locator("text=Golden Set")).not.toBeVisible();
  });
});
