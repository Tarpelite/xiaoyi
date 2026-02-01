import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    const ticker = searchParams.get('ticker');
    const date = searchParams.get('date');
    const range = searchParams.get('range') || '1';

    if (!ticker || !date) {
        return NextResponse.json({ error: 'Missing ticker or date parameter' }, { status: 400 });
    }

    const backendUrl = process.env.API_BASE_URL || 'http://localhost:8000';
    const url = `${backendUrl}/api/news?ticker=${ticker}&date=${date}&date_range=${range}`;

    try {
        const res = await fetch(url);
        if (!res.ok) {
            const errorText = await res.text();
            return NextResponse.json({ error: `Backend error: ${res.statusText}`, details: errorText }, { status: res.status });
        }
        const data = await res.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('Error proxying to backend:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
