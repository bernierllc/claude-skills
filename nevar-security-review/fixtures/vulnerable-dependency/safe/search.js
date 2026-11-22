// Search endpoint: parses the "q" query string as CLI-style flags (fixture).
const http = require("node:http");
const minimist = require("minimist");

http
  .createServer((req, res) => {
    const q = new URL(req.url, "http://localhost").searchParams.get("q") || "";
    const opts = minimist(q.split(" "));
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ terms: opts._, limit: Number(opts.limit) || 10 }));
  })
  .listen(0, "127.0.0.1");
