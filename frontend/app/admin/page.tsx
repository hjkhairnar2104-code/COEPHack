'use client';

import { useAuth } from '@/context/AuthContext';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useEffect, useState } from 'react';
import axios from 'axios';

export default function AdminPage() {
  const { token } = useAuth();
  const [users, setUsers] = useState([]);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await axios.get('http://localhost:8000/admin/users', {
          headers: { Authorization: `Bearer ${token}` },
        });
        setUsers(response.data);
      } catch (error) {
        console.error('Failed to fetch users', error);
      }
    };
    fetchUsers();
  }, [token]);

  return (
    <ProtectedRoute>
      <div className="container mx-auto p-8">
        <h1 className="text-2xl font-bold mb-4">Admin Panel</h1>
        <h2 className="text-xl mb-2">Users</h2>
        <table className="min-w-full bg-white border">
          <thead>
            <tr>
              <th className="border p-2">ID</th>
              <th className="border p-2">Email</th>
              <th className="border p-2">Role</th>
              <th className="border p-2">Active</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u: any) => (
              <tr key={u.id}>
                <td className="border p-2">{u.id}</td>
                <td className="border p-2">{u.email}</td>
                <td className="border p-2">{u.role}</td>
                <td className="border p-2">{u.active ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ProtectedRoute>
  );
}