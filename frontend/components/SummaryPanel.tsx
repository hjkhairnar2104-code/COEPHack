import React from 'react';
import Papa from 'papaparse';

interface SummaryProps {
  fileType: string;
  data: any[];
}

const SummaryPanel: React.FC<SummaryProps> = ({ fileType, data }) => {
  if (!data || data.length === 0) return null;

  const exportCSV = () => {
    // For CSV, convert adjustments arrays to strings
    const exportData = data.map(row => ({
      ...row,
      adjustments: row.adjustments ? row.adjustments.join('; ') : ''
    }));
    const csv = Papa.unparse(exportData);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${fileType}_summary.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (fileType === '835') {
    return (
      <div className="mt-6 p-4 border rounded-lg bg-blue-50">
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-bold text-lg">💰 Payment Summary</h3>
          <button
            onClick={exportCSV}
            className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm"
          >
            Export CSV
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="border p-2">Claim ID</th>
                <th className="border p-2">Billed</th>
                <th className="border p-2">Paid</th>
                <th className="border p-2">Patient Resp.</th>
                <th className="border p-2">Adjustment Reasons</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, idx) => (
                <tr key={idx} className={parseFloat(row.paid) > 0 ? 'bg-green-100' : 'bg-red-100'}>
                  <td className="border p-2">{row.claim_id}</td>
                  <td className="border p-2">{row.billed}</td>
                  <td className="border p-2">{row.paid}</td>
                  <td className="border p-2">{row.patient_responsibility}</td>
                  <td className="border p-2">
                    {row.adjustments && row.adjustments.length > 0 ? (
                      <ul className="list-disc list-inside text-xs">
                        {row.adjustments.map((adj: string, i: number) => (
                          <li key={i}>{adj}</li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (fileType === '834') {
    return (
      <div className="mt-6 p-4 border rounded-lg bg-green-50">
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-bold text-lg">📋 Member Enrollment Roster</h3>
          <button
            onClick={exportCSV}
            className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm"
          >
            Export CSV
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="border p-2">Member Name</th>
                <th className="border p-2">Action</th>
                <th className="border p-2">Effective Date</th>
                <th className="border p-2">Relationship</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, idx) => {
                let actionColor = '';
                if (row.action === 'Add') actionColor = 'text-green-600 font-bold';
                else if (row.action === 'Terminate') actionColor = 'text-red-600 font-bold';
                else if (row.action === 'Change') actionColor = 'text-yellow-600 font-bold';
                return (
                  <tr key={idx}>
                    <td className="border p-2">{row.member_name}</td>
                    <td className={`border p-2 ${actionColor}`}>{row.action}</td>
                    <td className="border p-2">{row.effective_date}</td>
                    <td className="border p-2">{row.relationship}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return null;
};

export default SummaryPanel;