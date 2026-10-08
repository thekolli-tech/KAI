export const surfaces = {
  chats: {
    title: "No conversations yet",
    detail:
      "Chats will be listed here after conversation persistence is connected. This phase does not store messages.",
  },
  projects: {
    title: "No projects yet",
    detail: "Projects are an organization-scoped boundary. None can be created in this phase.",
  },
  knowledge: {
    title: "Knowledge is not connected",
    detail:
      "Document upload, extraction, and retrieval are interfaces only. No files are ingested.",
  },
  agents: {
    title: "Agents are not running",
    detail:
      "Research, Coding, Data, and Document agents are defined and marked unimplemented. Nothing is executed from this screen.",
  },
  tools: {
    title: "Tools are not available",
    detail:
      "Calculator, web search, web fetch, file read, and file search are catalog entries. None of them run.",
  },
} as const;

export type SurfaceId = keyof typeof surfaces;
