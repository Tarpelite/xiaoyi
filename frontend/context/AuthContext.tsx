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
    isAuthenticated: boolean;
    isLoading: boolean;
    login: () => void;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    login: () => { },
    logout: () => { },
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<AuthingUser | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const login = useCallback(() => {
        window.location.href = '/api/auth/login';
    }, []);

    const logout = useCallback(() => {
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
                } else {
                    setUser(null);
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
