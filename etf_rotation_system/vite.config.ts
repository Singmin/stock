import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

function outputDataPlugin(): Plugin {
  const outputRoot = path.resolve(__dirname, "output");

  return {
    name: "serve-backtest-output",
    configureServer(server) {
      server.middlewares.use("/api/futu-sim-preview", (req, res) => {
        const rawUrl = req.url || "/";
        const url = new URL(rawUrl, "http://127.0.0.1");
        const mode = url.searchParams.get("mode") || "observe";
        const allowedModes = new Set(["observe", "cash-only", "full-account"]);

        if (req.method !== "POST") {
          res.statusCode = 405;
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.end(JSON.stringify({ ok: false, error: "Method not allowed" }));
          return;
        }

        if (!allowedModes.has(mode)) {
          res.statusCode = 400;
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.end(JSON.stringify({ ok: false, error: "Invalid preview mode" }));
          return;
        }

        const child = spawn("python", ["generate_futu_sim_orders.py", "--mode", mode, "--cash-buffer", "0.05"], {
          cwd: __dirname,
          windowsHide: true
        });
        let stdout = "";
        let stderr = "";

        child.stdout.on("data", (chunk) => {
          stdout += chunk.toString();
        });
        child.stderr.on("data", (chunk) => {
          stderr += chunk.toString();
        });
        child.on("error", (error) => {
          res.statusCode = 500;
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.end(JSON.stringify({ ok: false, mode, error: error.message, stdout, stderr }));
        });
        child.on("close", (code) => {
          res.statusCode = 200;
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.end(JSON.stringify({ ok: code === 0, mode, exitCode: code, stdout, stderr }));
        });
      });

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
