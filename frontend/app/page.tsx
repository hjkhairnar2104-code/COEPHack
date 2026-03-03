import FileUploader from '@/components/FileUploader';

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-50 py-8">
      <div className="container mx-auto">
        <h1 className="text-3xl font-bold text-center mb-2">
          US Healthcare EDI Parser
        </h1>
        <p className="text-center text-gray-600 mb-8">
          Upload 837, 835, or 834 files for validation
        </p>
        <FileUploader />
      </div>
    </main>
  );
}