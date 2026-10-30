import { expect, test } from "@playwright/test";

test.describe("OmniRun preflight", () => {
  test("happy path: real small public model with the manual hardware picker", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /The preflight layer/i }),
    ).toBeVisible();

    await page.getByRole("button", { name: /Run a preflight/i }).first().click();
    await page.locator("#model").fill("HuggingFaceTB/SmolLM2-135M-Instruct");
    await page.getByRole("tab", { name: /Pick my hardware/i }).click();
    await page.getByLabel("Search GPU or chip").fill("M2 Pro");
    await page.getByRole("button", { name: /Apple M2 Pro/i }).click();
    await page.locator("#ram-manual").fill("32");

    await expect(page.getByText("Apple M2 Pro · 32 GB RAM")).toBeVisible();
    await page.getByRole("button", { name: /^Run preflight$/ }).first().click();

    // A cached result can skip the visible loading stage; the result is the assertion.
    await expect(page.locator("#verdict-word")).toHaveText("GO", { timeout: 120_000 });
    await expect(page.getByText("Apple M2 Pro", { exact: false }).first()).toBeVisible();

    await expect(page.getByRole("heading", { name: "FITS", exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "SUPPORTED", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "VERIFIED", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("No recorded runs yet")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Artifacts" })).toBeVisible();
    await expect(page.locator(".artifact-row").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Budget and peak" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Speed" })).toBeVisible();
    await expect(page.getByText(/estimated|estimate/i).first()).toBeVisible();

    expect(page.url()).toContain("model=HuggingFaceTB%2FSmolLM2-135M-Instruct");
    expect(page.url()).toContain("run=1");
    expect(page.url()).not.toContain("hf_");
  });

  test("ASR returns UNKNOWN with an honest message", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Run a preflight/i }).first().click();
    await page.locator("#model").fill("openai/whisper-tiny");
    await page.getByRole("tab", { name: /CPU only/i }).click();
    await page.getByLabel("Total RAM", { exact: false }).last().fill("32");
    await page.getByRole("button", { name: /^Run preflight$/ }).first().click();

    await expect(page.locator("#verdict-word")).toHaveText("UNKNOWN", { timeout: 120_000 });
    await expect(page.getByText(/can’t judge ASR\/TTS yet/i)).toBeVisible();
    await expect(page.getByText("Speed estimate not available")).toBeVisible();
    await expect(page.getByText(/covers causal LLMs only/i).first()).toBeVisible();
  });

  test("invalid input is explained without a result", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Run a preflight/i }).first().click();
    await page.locator("#model").fill("https://huggingface.co/datasets/foo/bar");
    await page.getByRole("tab", { name: /CPU only/i }).click();
    await page.getByLabel("Total RAM", { exact: false }).last().fill("32");
    await page.getByRole("button", { name: /^Run preflight$/ }).first().click();

    await expect(page.locator("#check-error")).toBeVisible();
    await expect(page.getByText("That isn’t a model repo.")).toBeVisible();
    await expect(page.getByText(/only supports model repositories/i)).toBeVisible();
    await expect(page.locator("#verdict-word")).toHaveCount(0);
  });
});
