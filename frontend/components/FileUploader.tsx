'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import api from '@/lib/axios';
import { useAuth } from '@/context/AuthContext';
import ParsedEDIDisplay from './ParsedEDIDisplay';
import SummaryPanel from './SummaryPanel';

interface UploadResponse {
  file_id: string;
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

interface ValidationError {
  segment_id: string;
  element_index: number | null;
  severity: string;
  message: string;
  location: number | null;
}

interface FileUploaderProps {
  onUploadComplete?: (fileId: string, fileType: string) => void;
}

export default function FileUploader({ onUploadComplete }: FileUploaderProps) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [parsedData, setParsedData] = useState<any>(null);
  const [parsing, setParsing] = useState(false);
  const [errors, setErrors] = useState<ValidationError[]>([]);
  const [validating, setValidating] = useState(false);
  const [summaryData, setSummaryData] = useState<any[]>([]);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const { user } = useAuth();

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const file = acceptedFiles[0];
    setUploading(true);
    setError(null);
    setResult(null);
    setParsedData(null);
    setErrors([]);
    setSummaryData([]);

    const formData = new FormData();
    formData.append('file', file);

    try {
      // Upload
      const uploadRes = await api.post<UploadResponse>('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(uploadRes.data);

      // Parse
      setParsing(true);
      const parseRes = await api.post(`/parse/${uploadRes.data.file_id}`);
      setParsedData(parseRes.data);

      // Validate
      setValidating(true);
      const validateRes = await api.post(`/validate/${uploadRes.data.file_id}`);
      // Log errors for debugging
      console.log('Validation errors:', validateRes.data);
      setErrors(validateRes.data);

      // Summary (if 835 or 834)
      if (uploadRes.data.file_type === '835' || uploadRes.data.file_type === '834') {
        setSummaryLoading(true);
        try {
          const summaryRes = await api.post(`/summary/${uploadRes.data.file_id}`);
          setSummaryData(summaryRes.data);
        } catch (summaryErr) {
          console.error('Summary failed', summaryErr);
        } finally {
          setSummaryLoading(false);
        }
      }

      // Notify parent component about successful upload
      if (onUploadComplete) {
        onUploadComplete(uploadRes.data.file_id, uploadRes.data.file_type);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      setParsing(false);
      setValidating(false);
    }
  }, [onUploadComplete]);

  const downloadParsedJson = () => {
    if (!parsedData) return;
    const jsonStr = JSON.stringify(parsedData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `parsed-${result?.filename || 'edi'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.edi', '.txt', '.dat', '.x12'],
    },
    maxFiles: 1,
  });

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'error': return 'border-red-500 bg-red-50';
      case 'warning': return 'border-yellow-500 bg-yellow-50';
      case 'info': return 'border-blue-500 bg-blue-50';
      default: return 'border-gray-500 bg-gray-50';
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto p-4">
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
          ${uploading || parsing || validating || summaryLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mb-2"></div>
            <p>Uploading...</p>
          </div>
        ) : parsing ? (
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-green-500 mb-2"></div>
            <p>Parsing EDI file...</p>
          </div>
        ) : validating ? (
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-yellow-500 mb-2"></div>
            <p>Validating...</p>
          </div>
        ) : summaryLoading ? (
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-purple-500 mb-2"></div>
            <p>Generating summary...</p>
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

      {/* Summary Panel (for 835/834) */}
      {summaryLoading && <div className="mt-4 text-gray-500">Loading summary...</div>}
      {!summaryLoading && summaryData.length > 0 && (
        <SummaryPanel fileType={result?.file_type || ''} data={summaryData} />
      )}

      {/* Validation Errors */}
      {errors.length > 0 && (
        <div className="mt-6 p-4 border rounded-lg bg-red-50">
          <h3 className="font-bold text-lg mb-3 text-red-800">❌ Validation Errors ({errors.length})</h3>
          <div className="space-y-3 max-h-96 overflow-auto">
            {errors.map((err, idx) => (
              <div key={idx} className={`border-l-4 ${getSeverityColor(err.severity)} bg-white p-3 rounded shadow-sm`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-sm uppercase text-red-700">{err.severity || 'ERROR'}</span>
                  <span className="text-xs text-gray-500">
                    {err.segment_id}{err.element_index !== null ? `[${err.element_index}]` : ''} at segment {err.location}
                  </span>
                </div>
                <p className="text-sm text-gray-800">{err.message || 'No description provided.'}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Parsed Tree */}
      {parsedData && (
        <div className="mt-6 p-4 border rounded-lg bg-gray-50">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold text-lg">📄 Parsed EDI Structure</h3>
            <button
              onClick={downloadParsedJson}
              className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded text-sm"
            >
              Download JSON
            </button>
          </div>
          <div className="max-h-96 overflow-auto bg-white p-4 rounded border">
            <ParsedEDIDisplay data={parsedData} />
          </div>
        </div>
      )}
    </div>
  );
}