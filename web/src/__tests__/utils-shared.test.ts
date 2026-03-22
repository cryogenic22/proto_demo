import { describe, it, expect } from "vitest";
import { phaseVariant, formatCurrency, formatDate } from "@/lib/utils";

describe("phaseVariant", () => {
  it("returns info for Phase 1", () => {
    expect(phaseVariant("Phase 1")).toBe("info");
  });
  it("returns success for Phase 3", () => {
    expect(phaseVariant("Phase 3")).toBe("success");
  });
  it("returns neutral for unknown", () => {
    expect(phaseVariant("Unknown")).toBe("neutral");
  });
});

describe("formatCurrency", () => {
  it("formats USD correctly", () => {
    const result = formatCurrency(1234.56);
    expect(result).toContain("1,234");
  });
});

describe("formatDate", () => {
  it("formats ISO date string", () => {
    const result = formatDate("2025-01-15T00:00:00Z");
    expect(result).toContain("2025");
  });
  it("handles invalid input gracefully", () => {
    const result = formatDate("not-a-date");
    expect(result).toBe("not-a-date");
  });
});
