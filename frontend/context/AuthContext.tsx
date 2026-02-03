'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

// Define the User interface
interface AuthingUser {
    sub: string;
    email?: string;
    username?: string;
    picture?: string;
    [key: string]: any;
}

interface AuthContextType {
    user: AuthingUser | null;
    accessToken: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: () => void;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    accessToken: null,
    isAuthenticated: false,
    isLoading: true,
    login: () => { },
    logout: () => { },
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<AuthingUser | null>(null);
    const [accessToken, setAccessToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const login = useCallback(() => {
        window.location.href = '/api/auth/login';
    }, []);

    const logout = useCallback(() => {
        // Clear local storage
        if (typeof window !== 'undefined') {
            localStorage.removeItem('authing_access_token');
        }
        window.location.href = '/api/auth/logout';
    }, []);

    // Check auth status on mount
    useEffect(() => {
        const checkAuth = async () => {
            try {
                const res = await fetch('/api/auth/me');
                if (res.ok) {
                    const data = await res.json();
                    setUser(data.user);

                    // Store access token if available
                    if (data.accessToken) {
                        setAccessToken(data.accessToken);
                        if (typeof window !== 'undefined') {
                            localStorage.setItem('authing_access_token', data.accessToken);
                        }
                    }
                } else {
                    setUser(null);
                    setAccessToken(null);
                    if (typeof window !== 'undefined') {
                        localStorage.removeItem('authing_access_token');
                    }
                }
            } catch (error) {
                console.error('Failed to check auth status:', error);
                setUser(null);
            } finally {
                setIsLoading(false);
            }
        };

        checkAuth();
    }, []);

    const value = {
        user,
        accessToken,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
