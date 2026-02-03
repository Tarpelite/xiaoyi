import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const APP_ID = process.env.AUTHING_APP_ID || process.env.NEXT_PUBLIC_AUTHING_APP_ID;
const APP_SECRET = process.env.AUTHING_APP_SECRET;

// 域名 (用于登录页跳转) - 必须包含 AppID 后缀
const DOMAIN = process.env.NEXT_PUBLIC_AUTHING_DOMAIN || process.env.AUTHING_ISSUER?.replace(/\/oidc$/, '');

// OIDC 发行者 (用于 API 调用) - 必须包含 /oidc
const ISSUER = process.env.NEXT_PUBLIC_AUTHING_ISSUER || `${DOMAIN}/oidc`;

const REDIRECT_URI = process.env.NEXT_PUBLIC_AUTHING_REDIRECT_URI || `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000'}/api/auth/callback`;

export async function GET(request: NextRequest, { params }: { params: { authing: string[] } }) {
    const slug = params.authing[0];

    console.log('[Auth] Slug:', slug);
    console.log('[Auth] Config:', { DOMAIN, ISSUER, REDIRECT_URI, hasSecret: !!APP_SECRET });

    if (slug === 'login') {
        const params = new URLSearchParams({
            client_id: APP_ID!,
            redirect_uri: REDIRECT_URI,
            response_type: 'code',
            scope: 'openid profile email',
            nonce: `${Date.now()}`,
        });

        // Use standard OIDC auth endpoint
        // ISSUER ends with /oidc, so we append /auth -> .../oidc/auth
        const loginUrl = `${ISSUER}/auth?${params.toString()}`;
        console.log('[Auth] Redirecting to:', loginUrl);
        return NextResponse.redirect(loginUrl);
    }

    if (slug === 'callback') {
        const searchParams = request.nextUrl.searchParams;
        const code = searchParams.get('code');

        if (!code) {
            return NextResponse.json({ error: 'No code provided' }, { status: 400 });
        }

        try {
            // Note: ISSUER already includes /oidc
            const tokenRes = await fetch(`${ISSUER}/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({
                    client_id: APP_ID!,
                    client_secret: APP_SECRET!,
                    grant_type: 'authorization_code',
                    code,
                    redirect_uri: REDIRECT_URI,
                }).toString(),
            });

            const tokens = await tokenRes.json();
            console.log('[Auth] Token response:', tokens.error ? tokens.error : 'Success');

            if (tokens.error) {
                throw new Error(tokens.error_description || tokens.error);
            }

            // Get user info
            const userRes = await fetch(`${ISSUER}/me`, {
                headers: { Authorization: `Bearer ${tokens.access_token}` },
            });
            const user = await userRes.json();

            const response = NextResponse.redirect(new URL('/', request.url));

            // Set cookies
            response.cookies.set('authing_access_token', tokens.access_token, {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                path: '/',
                maxAge: tokens.expires_in,
            });

            // Also set a user cookie for client-side reading (non-httpOnly if needed, or just use an API to fetch)
            // Better: set httpOnly and expose /api/auth/me

            return response;
        } catch (error: any) {
            console.error('Auth check error', error);
            return NextResponse.json({ error: error.message }, { status: 500 });
        }
    }

    if (slug === 'logout') {
        const response = NextResponse.redirect(new URL('/', request.url));
        response.cookies.delete('authing_access_token');
        // Optional: redirect to Authing logout
        return response;
    }

    if (slug === 'me') {
        const cookieStore = cookies();
        const token = cookieStore.get('authing_access_token');

        if (!token) {
            return NextResponse.json({ user: null }, { status: 401 });
        }

        try {
            // Verify token or just decode? For now, we trust the token in the cookie or validate with Authing
            // Validation with Authing introspection or locally with JWKS is better
            // For performance, we can just return what we have or call userinfo
            // Let's call userinfo for now to be safe
            const userRes = await fetch(`${ISSUER}/me`, {
                headers: { Authorization: `Bearer ${token.value}` },
            });

            if (!userRes.ok) {
                return NextResponse.json({ user: null }, { status: 401 });
            }

            const user = await userRes.json();
            return NextResponse.json({ user });
        } catch (e) {
            return NextResponse.json({ user: null }, { status: 401 });
        }
    }

    return NextResponse.json({ error: 'Unknown route' }, { status: 404 });
}
