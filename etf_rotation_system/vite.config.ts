import fs from "node:fs";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

function outputDataPlugin(): Plugin {
  const outputRoot = path.resolve(__dirname, "output");

  return {
    name: "serve-backtest-output",
    configureServer(server) {
      server.middlewares.use("/output", (req, res) => {
        const rawUrl = req.url || "/";
        const decoded = decodeURIComponent(rawUrl.split("?")[0]);
        const cleanPath = decoded.replace(/^\/+/, "");
        const filePath = path.resolve(outputRoot, cleanPath);

        if (!filePath.startsWith(outputRoot)) {
          res.statusCode = 403;
          res.end("Forbidden");
          return;
        }

        if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
          res.statusCode = 404;
          res.end("Not found");
          return;
        }

        const ext = path.extname(filePath).toLowerCase();
        const type =
          ext === ".json"
            ? "application/json; charset=utf-8"
            : ext === ".csv"
              ? "text/csv; charset=utf-8"
              : "application/octet-stream";
        res.setHeader("Content-Type", type);
        fs.createReadStream(filePath).pipe(res);
      });
    }
  };
}

export default defineConfig({
  plugins: [react(), outputDataPlugin()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: false
  }
});
