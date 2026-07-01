import { describe, expect, it } from "vitest";
import { AxiosError } from "axios";
import { apiErrorMessage } from "../api/client";

describe("apiErrorMessage", () => {
  it("returns the FastAPI string detail", () => {
    const err = new AxiosError("Request failed");
    err.response = {
      data: { detail: "Device not found" },
      status: 404,
      statusText: "Not Found",
      headers: {},
      config: {} as never,
    };
    expect(apiErrorMessage(err)).toBe("Device not found");
  });

  it("returns the first validation error message", () => {
    const err = new AxiosError("Unprocessable");
    err.response = {
      data: { detail: [{ msg: "field required" }] },
      status: 422,
      statusText: "Unprocessable Entity",
      headers: {},
      config: {} as never,
    };
    expect(apiErrorMessage(err)).toBe("field required");
  });

  it("falls back for non-axios errors", () => {
    expect(apiErrorMessage(new Error("boom"))).toBe("Unexpected error");
  });
});
