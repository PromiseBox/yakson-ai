export const backendBaseUrl = (process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

const backendSharedSecret = (process.env.BACKEND_SHARED_SECRET ?? "").trim();

export function backendHeaders(headers?: HeadersInit) {
  const nextHeaders = new Headers(headers);
  if (backendSharedSecret) {
    nextHeaders.set("x-yakson-backend-secret", backendSharedSecret);
  }
  return nextHeaders;
}

export function backendUnavailableDetail(label = "백엔드 API") {
  return `${label}에 연결할 수 없습니다. 잠시 후 다시 시도해주세요. 문제가 계속되면 관리자에게 문의해주세요.`;
}
