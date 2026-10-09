// Render Web Service 용 정적 서버 (의존성 없음): dashboard 폴더를 제공한다.
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "dashboard");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".png": "image/png", ".css": "text/css; charset=utf-8" };

http.createServer((req, res) => {
  const urlPath = decodeURIComponent(req.url.split("?")[0]);
  const file = path.join(ROOT, urlPath === "/" ? "index.html" : urlPath);
  if (!file.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end("Not found"); }
    res.writeHead(200, {
      "Content-Type": TYPES[path.extname(file)] || "application/octet-stream",
      "Cache-Control": file.endsWith("data.js") ? "no-cache" : "public, max-age=3600",
    });
    res.end(data);
  });
}).listen(process.env.PORT || 10000, () => console.log("dashboard ready"));
