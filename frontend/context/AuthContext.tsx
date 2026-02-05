'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

// Define the User interface
interface AuthingUser {
    sub: string;
    email?: string;
    username?: string;
    name?: string;
    bio?: string;
    picture?: string;
    [key: string]: any;
}

interface AuthContextType {
    user: AuthingUser | null;
    accessToken: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    needsProfileCompletion: boolean;
    login: () => void;
    logout: () => void;
    updateUser: (updates: Partial<AuthingUser>) => void;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    accessToken: null,
    isAuthenticated: false,
    isLoading: true,
    needsProfileCompletion: false,
    login: () => { },
    logout: () => { },
    updateUser: () => { },
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<AuthingUser | null>(null);
    const [accessToken, setAccessToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [needsProfileCompletion, setNeedsProfileCompletion] = useState(false);

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

    const updateUser = useCallback((updates: Partial<AuthingUser>) => {
        setUser((prev) => {
            if (!prev) return prev;
            return { ...prev, ...updates };
        });
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

    // 检测用户是否需要补全资料
    useEffect(() => {
        if (user && !isLoading) {
            // 如果昵称为空或等于邮箱，说明需要补全
            const needsCompletion = !user.name || user.name === user.email || user.name.trim() === ''
            setNeedsProfileCompletion(needsCompletion)
        } else {
            setNeedsProfileCompletion(false)
        }
    }, [user, isLoading])

    return (
        <AuthContext.Provider value={{
            user,
            accessToken,
            isAuthenticated: !!user,
            isLoading,
            needsProfileCompletion,
            login,
            logout,
            updateUser,
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
