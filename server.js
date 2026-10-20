// Render Web Service 용 서버 (의존성 없음)
//  - dashboard 폴더 정적 제공
//  - POST /api/refresh        : GitHub Actions 수집 워크플로 실행 → 결과 커밋 시 Render 자동 재배포
//  - GET  /api/refresh-status : 최근 수집 실행 상태 + 현재 배포된 데이터 생성 시각
//  - /admin                   : 관리자 페이지 (로그인 후 갱신 버튼 표시)
//  - POST /api/admin/login · /api/admin/logout, GET /api/admin/me
// 환경변수: GITHUB_TOKEN (해당 저장소 Actions 읽기/쓰기 권한), GITHUB_REPO, GITHUB_WORKFLOW,
//          ADMIN_ID, ADMIN_PASSWORD (관리자 계정 — 공개 저장소에 올리지 말 것), SESSION_SECRET
const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "dashboard");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".png": "image/png", ".css": "text/css; charset=utf-8" };
const REPO = process.env.GITHUB_REPO || "yilowoon/AsanCity_NewsData";
const WORKFLOW = process.env.GITHUB_WORKFLOW || "daily.yml";
const TOKEN = process.env.GITHUB_TOKEN || "";
const COOLDOWN_MS = 10 * 60 * 1000;   // 버튼 남용 방지: 10분에 한 번
let lastTrigger = 0;

// ---------- 관리자 인증 ----------
const ADMIN_ID = process.env.ADMIN_ID || "";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "";
const SESSION_SECRET = process.env.SESSION_SECRET || crypto.randomBytes(32).toString("hex");
const SESSION_HOURS = 8;
const COOKIE = "asan_admin";
const failures = new Map();   // ip → { count, until }  로그인 연속 실패 시 잠금

const sha = v => crypto.createHash("sha256").update(String(v)).digest();
const same = (a, b) => crypto.timingSafeEqual(sha(a), sha(b));
const sign = v => crypto.createHmac("sha256", SESSION_SECRET).update(v).digest("base64url");

function issueSession(res, req) {
  const exp = String(Date.now() + SESSION_HOURS * 3600 * 1000);
  const secure = (req.headers["x-forwarded-proto"] || "").includes("https") ? "; Secure" : "";
  res.setHeader("Set-Cookie", `${COOKIE}=${exp}.${sign(exp)}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${SESSION_HOURS * 3600}${secure}`);
}
function isAdmin(req) {
  const m = (req.headers.cookie || "").match(/(?:^|;\s*)asan_admin=(\d+)\.([\w-]+)/);
  return !!m && Number(m[1]) > Date.now() && same(m[2], sign(m[1]));
}
function clientIp(req) {
  return (req.headers["x-forwarded-for"] || req.socket.remoteAddress || "").split(",")[0].trim();
}
function readBody(req) {
  return new Promise(resolve => {
    let data = "";
    req.on("data", c => { data += c; if (data.length > 10_000) req.destroy(); });
    req.on("end", () => { try { resolve(JSON.parse(data || "{}")); } catch (e) { resolve({}); } });
  });
}

async function adminApi(req, res, urlPath) {
  if (urlPath === "/api/admin/me") return json(res, 200, { admin: isAdmin(req) });
  if (urlPath === "/api/admin/logout" && req.method === "POST") {
    res.setHeader("Set-Cookie", `${COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0`);
    return json(res, 200, { ok: true });
  }
  if (urlPath === "/api/admin/login" && req.method === "POST") {
    if (!ADMIN_ID || !ADMIN_PASSWORD) return json(res, 503, { message: "서버에 관리자 계정(ADMIN_ID, ADMIN_PASSWORD)이 설정되지 않았습니다." });
    const ip = clientIp(req), f = failures.get(ip) || { count: 0, until: 0 };
    if (f.until > Date.now()) return json(res, 429, { message: `로그인 시도가 많아 잠겼습니다. ${Math.ceil((f.until - Date.now()) / 60000)}분 후 다시 시도하세요.` });
    const { id, password } = await readBody(req);
    if (same(id || "", ADMIN_ID) && same(password || "", ADMIN_PASSWORD)) {
      failures.delete(ip);
      issueSession(res, req);
      return json(res, 200, { ok: true });
    }
    f.count += 1;
    if (f.count >= 5) { f.until = Date.now() + 15 * 60 * 1000; f.count = 0; }
    failures.set(ip, f);
    return json(res, 401, { message: "아이디 또는 비밀번호가 올바르지 않습니다." });
  }
  return json(res, 404, { message: "Not found" });
}

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
  if (urlPath.startsWith("/api/admin/")) return adminApi(req, res, urlPath);
  if (!isAdmin(req)) return json(res, 401, { message: "관리자 로그인이 필요합니다." });
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
  if (urlPath === "/admin/") { res.writeHead(301, { Location: "/admin" }); return res.end(); }
  const page = urlPath === "/" || urlPath === "/admin" ? "index.html" : urlPath;
  const file = path.join(ROOT, page);
  if (!file.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end("Not found"); }
    res.writeHead(200, {
      "Content-Type": TYPES[path.extname(file)] || "application/octet-stream",
      "Cache-Control": /\.(js|html)$/.test(file) ? "no-cache" : "public, max-age=3600",
    });
    if (file.endsWith(".html")) {
      // 공유 미리보기(og:image 등)는 절대 URL 이 필요하므로 접속 도메인으로 채운다
      const proto = (req.headers["x-forwarded-proto"] || "http").split(",")[0].trim();
      const origin = process.env.PUBLIC_URL || `${proto}://${req.headers.host}`;
      return res.end(data.toString("utf8").replaceAll("%%ORIGIN%%", origin.replace(/\/+$/, "")));
    }
    res.end(data);
  });
}).listen(process.env.PORT || 10000, () => console.log("dashboard ready"));
