import type { NextConfig } from "next";

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api").replace(/\/+$/, "");
const apiProxyTarget = apiBaseUrl.startsWith("/") ? "http://127.0.0.1:8000/api" : apiBaseUrl;

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/:path*`
      }
    ];
  },
  webpack: (config) => {
    config.resolve.alias = {
      ...(config.resolve.alias ?? {}),
      canvas: false
    };
    return config;
  }
};

export default nextConfig;
