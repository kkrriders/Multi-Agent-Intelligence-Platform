import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Minimal runtime image: `.next/standalone` bundles only what the server
  // needs, so the Docker runtime stage skips node_modules entirely.
  output: "standalone",
};

export default nextConfig;
