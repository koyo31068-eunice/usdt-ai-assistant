/**
 * Vercel 배포용 빌드 스크립트
 * - 환경 변수 API_BASE_URL 로 config.js 를 만들고, 배포할 파일을 dist 폴더에 모읍니다.
 * - Vercel 이 배포할 때 자동으로 실행합니다 (vercel.json 의 buildCommand).
 * - 로컬에서는 실행할 필요 없습니다 (로컬은 config.js 를 직접 사용).
 */
const fs = require("fs");
const path = require("path");

const url = (process.env.API_BASE_URL || "").trim().replace(/\/+$/, "");
if (!/^https?:\/\//.test(url)) {
  console.error("❌ API_BASE_URL 환경 변수가 없거나 형식이 틀렸습니다. 예: https://내서버.onrender.com");
  process.exit(1);
}

const out = path.join(__dirname, "dist");
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out);

for (const f of ["index.html", "style.css", "app.js"]) {
  fs.copyFileSync(path.join(__dirname, f), path.join(out, f));
}
fs.writeFileSync(
  path.join(out, "config.js"),
  `window.APP_CONFIG = { API_BASE_URL: ${JSON.stringify(url)} };\n`
);
console.log("✅ dist/config.js 생성 완료 →", url);