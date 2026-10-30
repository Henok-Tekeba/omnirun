import { expect, test } from "@playwright/test";

test.describe("OmniRun preflight", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem("omnirun.cookie-consent", "essential");
      } catch {
        /* Storage can be unavailable. */
      }
    });
  });

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
    await expect(page.getByRole("heading", { name: "What if?" })).toBeVisible();
    await expect(page.getByText("Max context that fits")).toBeVisible();
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

  test("finder ranks candidates and opens one in preflight", async ({ page }) => {
    await page.route("**/api/find", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          schema_version: "1.0",
          request_id: "test-find",
          searched: 1,
          errors: [],
          candidates: [
            {
              repo_id: "org/model",
              license: "apache-2.0",
              pipeline_tag: "text-generation",
              library_name: "transformers",
              model_class: "llm",
              format: "safetensors",
              gated: false,
              private: false,
              trust_remote_code_required: false,
              verdict: "GO",
              confidence: "medium",
              fits: "yes",
              supported: "yes",
              verified: "unknown",
              direct_runtime_available: true,
              memory_budget_bytes: 25769803776,
              peak: { min: 600000000, likely: 640000000, max: 690000000 },
              speed: { min: 300, likely: 380, max: 460 },
              artifacts_count: 2,
              best_artifact: "model.safetensors",
              best_artifact_size_bytes: 269060552,
              reason: "Fits and has a direct runtime path.",
            },
          ],
        }),
      });
    });

    await page.goto("/");
    await page.getByRole("button", { name: /Run a preflight/i }).first().click();
    await page.getByRole("tab", { name: /CPU only/i }).click();
    await page.getByLabel("Total RAM", { exact: false }).last().fill("32");
    await page
      .locator(".dashboard-sidebar")
      .getByRole("button", { name: "Find models" })
      .click();
    await page.locator("#dashboard-content").getByRole("button", { name: "Find models" }).click();
    await expect(page.locator(".finder-card")).toBeVisible();
    await expect(page.getByText("org/model")).toBeVisible();
    await page.getByRole("button", { name: /Open in preflight/i }).click();
    await expect(page.locator("#model")).toHaveValue("org/model");
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
