import { NextResponse } from "next/server";

const backendBaseUrl = (process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

async function proxy(request: Request, context: RouteContext) {
  const { path } = await context.params;
  const requestUrl = new URL(request.url);
  const targetUrl = `${backendBaseUrl}/api/${path.join("/")}${requestUrl.search}`;
  const method = request.method;
  const hasBody = !["GET", "HEAD"].includes(method);

  try {
    const response = await fetch(targetUrl, {
      method,
      headers: {
        Accept: request.headers.get("accept") ?? "application/json",
        "Content-Type": request.headers.get("content-type") ?? "application/json"
      },
      body: hasBody ? await request.text() : undefined,
      cache: "no-store"
    });

    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    const contentType = response.headers.get("content-type") ?? "application/json";
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type": contentType
      }
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          "백엔드 API에 연결할 수 없습니다. FastAPI를 8000번 포트로 실행하거나 BACKEND_API_BASE_URL을 설정해주세요."
      },
      { status: 503 }
    );
  }
}

export function GET(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export function POST(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export function PATCH(request: Request, context: RouteContext) {
  return proxy(request, context);
}

export function DELETE(request: Request, context: RouteContext) {
  return proxy(request, context);
}
