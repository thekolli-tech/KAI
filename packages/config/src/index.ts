import kaiConfig from "../kai.config.json" with { type: "json" };

export { kaiConfig };

export const defaultApiOrigin = `http://localhost:${kaiConfig.ports.api}`;
