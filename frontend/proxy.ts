import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export default function proxy(request: NextRequest) {
  const token = request.cookies.get('access_token')?.value;
  // For simplicity, we'll rely on client‑side protection for now.
  return NextResponse.next();
}