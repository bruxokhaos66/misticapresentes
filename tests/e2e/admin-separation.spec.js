const { test, expect } = require("@playwright/test");

test("public index.html never ships the admin markup/scripts", async ({ page }) => {
  const requests = [];
  page.on("request", (r) => requests.push(r.url()));
  await page.goto("/index.html", { waitUntil: "networkidle" });
  await expect(page.locator("#admin")).toHaveCount(0);
  expect(requests.some((u) => u.includes("v2-admin-products"))).toBe(false);
  expect(requests.some((u) => u.includes("v2-courses"))).toBe(false);
});

test("old #admin hash on index.html redirects to admin.html", async ({ page }) => {
  await page.goto("/index.html#admin", { waitUntil: "networkidle" });
  await expect(page).toHaveURL(/admin\.html$/);
});

test("admin.html loads the login panel and the on-demand admin assets", async ({ page }) => {
  const requests = [];
  page.on("request", (r) => requests.push(r.url()));
  await page.goto("/admin.html", { waitUntil: "networkidle" });
  await expect(page.locator("#adminLoginForm")).toHaveCount(1);
  await expect(page.locator("#adminContent")).toBeHidden();
  await expect(page.locator("#adminUserLogin")).toHaveCount(1);
  expect(requests.some((u) => u.includes("v2-admin-products.css"))).toBe(true);
  expect(requests.some((u) => u.includes("v2-admin-products.js"))).toBe(true);
  expect(requests.some((u) => u.includes("v2-courses.css"))).toBe(true);
  expect(requests.some((u) => u.includes("v2-courses.js"))).toBe(true);
});
