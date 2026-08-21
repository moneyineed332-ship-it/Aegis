import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Card, CardHeader, Button, Badge, Stat, EmptyState, Skeleton, SkeletonCard } from "./index";

describe("Card", () => {
  it("renders children", () => {
    render(<Card><p>Content</p></Card>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    render(<Card className="custom-class"><p>Content</p></Card>);
    expect(screen.getByText("Content").closest("div")).toHaveClass("custom-class");
  });

  it("calls onClick when clickable", () => {
    const onClick = vi.fn();
    render(<Card onClick={onClick}><p>Content</p></Card>);
    fireEvent.click(screen.getByText("Content").closest("div")!);
    expect(onClick).toHaveBeenCalled();
  });

  it("has button role when clickable", () => {
    render(<Card onClick={() => {}}><p>Content</p></Card>);
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("does not have button role when not clickable", () => {
    render(<Card><p>Content</p></Card>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("supports hoverable state", () => {
    render(<Card hoverable><p>Content</p></Card>);
    const card = screen.getByText("Content").closest("div")!;
    expect(card.className).toContain("hover:border-primary/20");
  });
});

describe("CardHeader", () => {
  it("renders title", () => {
    render(<CardHeader title="Test Title" />);
    expect(screen.getByText("Test Title")).toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    render(<CardHeader title="Title" icon={<span data-testid="icon">★</span>} />);
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });

  it("renders action when provided", () => {
    render(<CardHeader title="Title" action={<button>Action</button>} />);
    expect(screen.getByText("Action")).toBeInTheDocument();
  });

  it("hides icon container when no icon", () => {
    const { container } = render(<CardHeader title="Title" />);
    expect(container.querySelector(".w-7.h-7")).not.toBeInTheDocument();
  });
});

describe("Button", () => {
  it("renders text", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  it("calls onClick", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    fireEvent.click(screen.getByText("Click"));
    expect(onClick).toHaveBeenCalled();
  });

  it("is disabled when disabled prop is true", () => {
    render(<Button disabled>Click</Button>);
    expect(screen.getByText("Click")).toBeDisabled();
  });

  it("is disabled when loading", () => {
    render(<Button loading>Loading</Button>);
    expect(screen.getByText("Loading")).toBeDisabled();
  });

  it("shows spinner when loading", () => {
    const { container } = render(<Button loading>Loading</Button>);
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    render(<Button icon={<span data-testid="icon">→</span>}>With Icon</Button>);
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });

  it("applies variant styles", () => {
    render(<Button variant="danger">Danger</Button>);
    const btn = screen.getByText("Danger");
    expect(btn.className).toContain("bg-destructive/10");
  });

  it("applies size styles", () => {
    render(<Button size="lg">Large</Button>);
    const btn = screen.getByText("Large");
    expect(btn.className).toContain("px-4");
  });
});

describe("Badge", () => {
  it("renders text", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("applies default variant", () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText("Default").className).toContain("bg-secondary");
  });

  it("applies success variant", () => {
    render(<Badge variant="success">OK</Badge>);
    expect(screen.getByText("OK").className).toContain("bg-success/10");
  });

  it("applies danger variant", () => {
    render(<Badge variant="danger">Error</Badge>);
    expect(screen.getByText("Error").className).toContain("bg-destructive/10");
  });

  it("applies warning variant", () => {
    render(<Badge variant="warning">Warn</Badge>);
    expect(screen.getByText("Warn").className).toContain("bg-warning/10");
  });

  it("applies info variant", () => {
    render(<Badge variant="info">Info</Badge>);
    expect(screen.getByText("Info").className).toContain("bg-primary/10");
  });
});

describe("Stat", () => {
  it("renders label and value", () => {
    render(<Stat label="Cycles" value={42} />);
    expect(screen.getByText("Cycles")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders positive change", () => {
    render(<Stat label="PnL" value="$100" change={5.25} />);
    expect(screen.getByText("+5.25%")).toBeInTheDocument();
  });

  it("renders negative change", () => {
    render(<Stat label="PnL" value="$-50" change={-3.14} />);
    expect(screen.getByText("-3.14%")).toBeInTheDocument();
  });

  it("hides change when undefined", () => {
    const { container } = render(<Stat label="X" value="Y" />);
    expect(container.querySelector(".text-success")).not.toBeInTheDocument();
    expect(container.querySelector(".text-destructive")).not.toBeInTheDocument();
  });

  it("applies custom className", () => {
    render(<Stat label="X" value="Y" className="custom" />);
    expect(screen.getByText("X").closest("div")?.parentElement).toHaveClass("custom");
  });
});

describe("EmptyState", () => {
  it("renders title", () => {
    render(<EmptyState title="No data" />);
    expect(screen.getByText("No data")).toBeInTheDocument();
  });

  it("renders description when provided", () => {
    render(<EmptyState title="Empty" description="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    render(<EmptyState title="Empty" icon={<span data-testid="icon">📭</span>} />);
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });

  it("hides description when not provided", () => {
    render(<EmptyState title="Only title" />);
    expect(screen.queryByText("Nothing here")).not.toBeInTheDocument();
  });
});

describe("Skeleton", () => {
  it("renders with animate-pulse", () => {
    const { container } = render(<Skeleton className="h-4 w-full" />);
    expect(container.firstChild).toHaveClass("animate-pulse");
  });
});

describe("SkeletonCard", () => {
  it("renders default rows", () => {
    const { container } = render(<SkeletonCard />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBe(4); // 1 header + 3 rows
  });

  it("renders custom row count", () => {
    const { container } = render(<SkeletonCard rows={5} />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBe(6); // 1 header + 5 rows
  });
});
