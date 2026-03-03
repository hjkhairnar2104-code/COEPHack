'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import api from '@/lib/axios';  // 👈 import the configured axios instance
import { useAuth } from '@/context/AuthContext'; // optional: to show role messages

interface UploadResponse {
  filename: string;
  file_type: string;
  metadata: {
    sender_id: string;
    receiver_id: string;
    interchange_date: string;
    transaction_count: number;
  };
  file_size: number;
  message: string;
}

export default function FileUploader() {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth(); // optional: get current user role for UI hints

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const file = acceptedFiles[0];
    setUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      // Use api instead of axios
      const response = await api.post<UploadResponse>('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.edi', '.txt', '.dat', '.x12']
    },
    maxFiles: 1,
  });

  return (
    <div className="w-full max-w-2xl mx-auto p-4">
      {/* Optional role hint */}
      {user?.role === 'billing_specialist' && (
        <p className="text-sm text-blue-600 mb-2">You can only upload 837 files.</p>
      )}
      {user?.role === 'benefits_admin' && (
        <p className="text-sm text-green-600 mb-2">You can only upload 834 files.</p>
      )}

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
          ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mb-2"></div>
            <p>Uploading...</p>
          </div>
        ) : isDragActive ? (
          <p>Drop the EDI file here...</p>
        ) : (
          <div>
            <p className="text-lg mb-2">Drag & drop an EDI file here</p>
            <p className="text-sm text-gray-500">or click to select</p>
            <p className="text-xs text-gray-400 mt-2">
              Supported: .edi, .txt, .dat, .x12
            </p>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          ❌ {error}
        </div>
      )}

      {result && (
        <div className="mt-6 p-4 border rounded-lg bg-green-50">
          <h3 className="font-bold text-lg mb-3">✅ Upload Successful</h3>
          <div className="space-y-2">
            <p><span className="font-semibold">Filename:</span> {result.filename}</p>
            <p>
              <span className="font-semibold">File Type:</span>{' '}
              <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                {result.file_type}
              </span>
            </p>
            <div className="mt-3 pt-3 border-t">
              <h4 className="font-medium mb-2">📋 Envelope Metadata</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <span className="text-gray-600">Sender ID:</span>
                <span className="font-mono">{result.metadata.sender_id}</span>
                <span className="text-gray-600">Receiver ID:</span>
                <span className="font-mono">{result.metadata.receiver_id}</span>
                <span className="text-gray-600">Interchange Date:</span>
                <span>{result.metadata.interchange_date}</span>
                <span className="text-gray-600">Transaction Count:</span>
                <span>{result.metadata.transaction_count}</span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              File size: {(result.file_size / 1024).toFixed(2)} KB
            </p>
          </div>
        </div>
      )}
    </div>
  );
}