import { NextResponse } from "next/server";

import { backendBaseUrl, backendHeaders, backendUnavailableDetail } from "../_backend";

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
  const headers = backendHeaders({
    Accept: request.headers.get("accept") ?? "application/json"
  });
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }

  try {
    const response = await fetch(targetUrl, {
      method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
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
        detail: backendUnavailableDetail()
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
