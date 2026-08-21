import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import BackToTop from "./BackToTop";

describe("BackToTop", () => {
  beforeEach(() => {
    vi.stubGlobal("scrollTo", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is hidden when scroll is below 400px", () => {
    Object.defineProperty(window, "scrollY", { value: 100, writable: true });
    render(<BackToTop />);
    expect(screen.queryByLabelText("Retour en haut")).not.toBeInTheDocument();
  });

  it("appears when scroll exceeds 400px", () => {
    Object.defineProperty(window, "scrollY", { value: 500, writable: true });
    render(<BackToTop />);
    fireEvent.scroll(window);
    expect(screen.getByLabelText("Retour en haut")).toBeInTheDocument();
  });

  it("scrolls to top when clicked", () => {
    Object.defineProperty(window, "scrollY", { value: 500, writable: true });
    render(<BackToTop />);
    fireEvent.scroll(window);
    fireEvent.click(screen.getByLabelText("Retour en haut"));
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
  });

  it("hides again when scroll goes back below 400px", () => {
    Object.defineProperty(window, "scrollY", { value: 500, writable: true });
    render(<BackToTop />);
    fireEvent.scroll(window);
    expect(screen.getByLabelText("Retour en haut")).toBeInTheDocument();

    Object.defineProperty(window, "scrollY", { value: 100, writable: true });
    fireEvent.scroll(window);
    expect(screen.queryByLabelText("Retour en haut")).not.toBeInTheDocument();
  });
});
