// Render Web Service 용 서버 (의존성 없음)
//  - dashboard 폴더 정적 제공
//  - POST /api/refresh        : GitHub Actions 수집 워크플로 실행 → 결과 커밋 시 Render 자동 재배포
//  - GET  /api/refresh-status : 최근 수집 실행 상태 + 현재 배포된 데이터 생성 시각
// 환경변수: GITHUB_TOKEN (해당 저장소 Actions 읽기/쓰기 권한), GITHUB_REPO, GITHUB_WORKFLOW
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "dashboard");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".png": "image/png", ".css": "text/css; charset=utf-8" };
const REPO = process.env.GITHUB_REPO || "yilowoon/AsanCity_NewsData";
const WORKFLOW = process.env.GITHUB_WORKFLOW || "daily.yml";
const TOKEN = process.env.GITHUB_TOKEN || "";
const COOLDOWN_MS = 10 * 60 * 1000;   // 버튼 남용 방지: 10분에 한 번
let lastTrigger = 0;

// 이 배포에 포함된 데이터의 생성 시각 (재배포되면 바뀐다)
let dataVersion = "";
try {
  const head = fs.readFileSync(path.join(ROOT, "data.js"), "utf8").slice(0, 2000);
  dataVersion = (head.match(/"generated":"([^"]+)"/) || [])[1] || "";
} catch (e) {}

function json(res, code, body) {
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
  res.end(JSON.stringify(body));
}

async function github(method, url, body) {
  const r = await fetch(`https://api.github.com/repos/${REPO}${url}`, {
    method,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "asan-pr-dashboard",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok && r.status !== 204) throw new Error(`GitHub API ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.status === 204 ? null : r.json();
}

async function latestRun() {
  const data = await github("GET", `/actions/workflows/${WORKFLOW}/runs?per_page=1`);
  const run = data.workflow_runs && data.workflow_runs[0];
  return run ? { status: run.status, conclusion: run.conclusion, createdAt: run.created_at, updatedAt: run.updated_at, event: run.event } : null;
}

async function api(req, res, urlPath) {
  if (!TOKEN) return json(res, 503, { enabled: false, message: "서버에 GITHUB_TOKEN 이 설정되지 않았습니다." });
  try {
    if (urlPath === "/api/refresh-status" && req.method === "GET") {
      return json(res, 200, { enabled: true, dataVersion, run: await latestRun() });
    }
    if (urlPath === "/api/refresh" && req.method === "POST") {
      const run = await latestRun();
      if (run && run.status !== "completed") return json(res, 200, { started: false, message: "이미 수집이 진행 중입니다.", run, dataVersion });
      const wait = lastTrigger + COOLDOWN_MS - Date.now();
      if (wait > 0) return json(res, 429, { started: false, message: `잠시 후 다시 시도하세요 (${Math.ceil(wait / 60000)}분 후).`, dataVersion });
      await github("POST", `/actions/workflows/${WORKFLOW}/dispatches`, { ref: "main" });
      lastTrigger = Date.now();
      return json(res, 202, { started: true, message: "수집을 시작했습니다.", dataVersion });
    }
    return json(res, 404, { message: "Not found" });
  } catch (e) {
    console.error(e);
    return json(res, 502, { message: "갱신 요청에 실패했습니다.", detail: String(e.message || e) });
  }
}

http.createServer((req, res) => {
  const urlPath = decodeURIComponent(req.url.split("?")[0]);
  if (urlPath.startsWith("/api/")) return api(req, res, urlPath);
  const file = path.join(ROOT, urlPath === "/" ? "index.html" : urlPath);
  if (!file.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end("Not found"); }
    res.writeHead(200, {
      "Content-Type": TYPES[path.extname(file)] || "application/octet-stream",
      "Cache-Control": /\.(js|html)$/.test(file) ? "no-cache" : "public, max-age=3600",
    });
    res.end(data);
  });
}).listen(process.env.PORT || 10000, () => console.log("dashboard ready"));
