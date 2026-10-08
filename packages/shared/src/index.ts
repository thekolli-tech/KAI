export const brand = {
  name: "KAI",
  maker: "THEKOLLI",
  tagline: "Your Unified AI Intelligence",
  prompt: "What can I help you with?",
} as const;

export const apiRoutes = {
  health: "/api/v1/health",
  probe: "/health",
} as const;

export const quickActions = [
  { id: "research", label: "Research", detail: "Web research" },
  { id: "analyze", label: "Analyze", detail: "Document intelligence" },
  { id: "write", label: "Write", detail: "Drafting" },
  { id: "code", label: "Code", detail: "Coding" },
  { id: "data", label: "Data", detail: "Data analysis" },
  { id: "create", label: "Create", detail: "Creation" },
] as const;
