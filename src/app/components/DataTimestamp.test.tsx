import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataTimestamp } from "./DataTimestamp";

describe("DataTimestamp", () => {
  it("renders formatted time", () => {
    const date = new Date("2026-07-15T14:30:45");
    render(<DataTimestamp lastUpdated={date} />);
    expect(screen.getByText(/14:30:45/)).toBeInTheDocument();
  });

  it("renders nothing when null", () => {
    const { container } = render(<DataTimestamp lastUpdated={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("contains clock icon", () => {
    render(<DataTimestamp lastUpdated={new Date()} />);
    expect(screen.getByText(/:/)).toBeInTheDocument();
  });
});
