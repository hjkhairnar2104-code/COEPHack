'use client';

import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';
import { jwtDecode } from 'jwt-decode';

interface User {
  email: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, role?: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    console.log('useEffect started');
    const storedToken = localStorage.getItem('access_token');
    if (storedToken) {
      try {
        const decoded: any = jwtDecode(storedToken);
        setToken(storedToken);
        setUser({ email: decoded.sub, role: decoded.role });
      } catch (error) {
        console.error('Invalid token', error);
        localStorage.removeItem('access_token');
      }
    }
    setIsLoading(false);
    console.log('isLoading set to false');
  }, []);

  const login = async (email: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await axios.post('http://localhost:8000/token', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    const { access_token } = response.data;
    localStorage.setItem('access_token', access_token);
    const decoded: any = jwtDecode(access_token);
    setToken(access_token);
    setUser({ email: decoded.sub, role: decoded.role });
  };

  const register = async (email: string, password: string, role: string = 'billing_specialist') => {
    await axios.post('http://localhost:8000/register', null, {
      params: { email, password, role },
    });
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};