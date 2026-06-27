import { ApiError } from "./api";

export const APP_ERROR_CODES = {
  authForbidden: "ERR-AUTH-FORBIDDEN",
  dbConnection: "ERR-DB-CONNECTION",
  invalidRequest: "ERR-INVALID-REQUEST",
  network: "ERR-NETWORK",
  notFound: "ERR-NOT-FOUND",
  requestFailed: "ERR-REQUEST-FAILED",
  server: "ERR-SERVER",
  serviceUnavailable: "ERR-SERVICE-UNAVAILABLE",
  unknown: "ERR-UNKNOWN"
} as const;

type AppErrorCode = (typeof APP_ERROR_CODES)[keyof typeof APP_ERROR_CODES];

function classifyAppError(caught: unknown): AppErrorCode {
  if (caught instanceof ApiError) {
    const message = caught.message.toLowerCase();

    if (
      message.includes("cloud sql") ||
      message.includes("database_url") ||
      message.includes("db에 연결") ||
      message.includes("database")
    ) {
      return APP_ERROR_CODES.dbConnection;
    }

    if (caught.status === 401 || caught.status === 403) {
      return APP_ERROR_CODES.authForbidden;
    }

    if (caught.status === 404) {
      return APP_ERROR_CODES.notFound;
    }

    if (caught.status === 400 || caught.status === 422) {
      return APP_ERROR_CODES.invalidRequest;
    }

    if (caught.status === 503) {
      return APP_ERROR_CODES.serviceUnavailable;
    }

    if (caught.status >= 500) {
      return APP_ERROR_CODES.server;
    }

    return APP_ERROR_CODES.requestFailed;
  }

  if (caught instanceof TypeError) {
    return APP_ERROR_CODES.network;
  }

  return APP_ERROR_CODES.unknown;
}

export function toUserErrorMessage(caught: unknown, fallbackMessage: string) {
  const code = classifyAppError(caught);

  if (code === APP_ERROR_CODES.dbConnection) {
    return `DB에 연결할 수 없습니다. 오류코드: ${code}`;
  }

  return `${fallbackMessage} 오류코드: ${code}`;
}
