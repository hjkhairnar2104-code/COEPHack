'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import ChatPanel from '../../../components/ChatPanel';

export default function ChatPage() {
  const params = useParams();
  const fileId = params.fileId as string;

  return (
    <div className="container mx-auto p-4">
      <div className="mb-4 flex items-center gap-4">
        <Link href="/" className="text-blue-600 hover:underline">
          ← Back to Upload
        </Link>
      </div>
      <h1 className="text-2xl font-bold mb-4">AI Assistant – Chat about your file</h1>
      <ChatPanel fileId={fileId} />
    </div>
  );
}