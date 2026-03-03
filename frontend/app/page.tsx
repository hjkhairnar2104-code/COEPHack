'use client';

import { useAuth } from '@/context/AuthContext';
import ProtectedRoute from '@/components/ProtectedRoute';
import FileUploader from '@/components/FileUploader';
import Link from 'next/link';

export default function Home() {
  const { user, logout } = useAuth();

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-50">
        <nav className="bg-white shadow p-4">
          <div className="container mx-auto flex justify-between items-center">
            <h1 className="text-xl font-bold">EDI Parser</h1>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                {user?.email} ({user?.role})
              </span>
              {user?.role === 'admin' && (
                <Link href="/admin" className="text-blue-500 hover:underline">
                  Admin Panel
                </Link>
              )}
              <button
                onClick={logout}
                className="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600 text-sm"
              >
                Logout
              </button>
            </div>
          </div>
        </nav>

        <main className="container mx-auto py-8">
          <h2 className="text-3xl font-bold text-center mb-2">
            US Healthcare EDI Parser
          </h2>
          <p className="text-center text-gray-600 mb-8">
            Upload 837, 835, or 834 files for validation
          </p>

          {/* Optionally show role-specific messages */}
          {user?.role === 'billing_specialist' && (
            <p className="text-center text-sm text-blue-600 mb-4">
              You can only upload 837 files.
            </p>
          )}
          {user?.role === 'benefits_admin' && (
            <p className="text-center text-sm text-green-600 mb-4">
              You can only upload 834 files.
            </p>
          )}

          <FileUploader />
        </main>
      </div>
    </ProtectedRoute>
  );
}